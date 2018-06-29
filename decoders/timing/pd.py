##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2014 Torsten Duwe <duwe@suse.de>
## Copyright (C) 2014 Sebastien Bourdelin <sebastien.bourdelin@savoirfairelinux.com>
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation; either version 2 of the License, or
## (at your option) any later version.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with this program; if not, see <http://www.gnu.org/licenses/>.
##

import sigrokdecode as srd
from collections import deque

class SamplerateError(Exception):
    pass

def normalize_time(t):
    if abs(t) >= 1.0:
        return '%.3f s  (%.3f Hz)' % (t, (1/t))
    elif abs(t) >= 0.001:
        if 1/t/1000 < 1:
            return '%2.3f ms (%.3f Hz)' % (t * 1000.0, (1/t))
        else:
            return '%2.3f ms (%.3f kHz)' % (t * 1000.0, (1/t)/1000)
    elif abs(t) >= 0.000001:
        if 1/t/1000/1000 < 1:
            return '%2.3f μs (%.3f kHz)' % (t * 1000.0 * 1000.0, (1/t)/1000)
        else:
            return '%2.3f μs (%.3f MHz)' % (t * 1000.0 * 1000.0, (1/t)/1000/1000)
    elif abs(t) >= 0.000000001:
        if 1/t/1000/1000/1000:
            return '%2.3f ns (%.3f MHz)' % (t * 1000.0 * 1000.0 * 1000.0, (1/t)/1000/1000)
        else:
            return '%2.3f ns (%.3f GHz)' % (t * 1000.0 * 1000.0 * 1000.0, (1/t)/1000/1000/1000)
    else:
        return '%f' % t

class Decoder(srd.Decoder):
    api_version = 3
    id = 'timing'
    name = 'Timing'
    longname = 'Timing calculation with frequency and averaging'
    desc = 'Calculate time between edges.'
    license = 'gplv2+'
    inputs = ['logic']
    outputs = ['timing']
    channels = (
        {'id': 'data', 'name': 'Data', 'desc': 'Data line'},
    )
    annotations = (
        ('time', 'Time'),
        ('average', 'Average'),
        ('delta', 'Delta'),
        ('converted', 'Converted'),
    )
    annotation_rows = (
        ('time', 'Time', (0,)),
        ('average', 'Average', (1,)),
        ('delta', 'Delta', (2,)),
        ('converted', 'Converted', (3,)),
    )
    options = (
        { 'id': 'avg_period', 'desc': 'Averaging period', 'default': 100 },
        { 'id': 'edge', 'desc': 'Edges to check', 'default': 'any', 'values': ('any', 'rising', 'falling') },
        { 'id': 'delta', 'desc': 'Show delta from last', 'default': 'no', 'values': ('yes', 'no') },
        { 'id': 'conv_a', 'desc': 'Conversion factor a in y=x*a+b', 'default': 660},
        { 'id': 'conv_b', 'desc': 'Conversion factor b in y=x*a+b', 'default': 0},
    )

    conversion_a = 0
    conversion_b = 0

    def __init__(self):
        self.reset()

    def reset(self):
        self.samplerate = None
        self.last_samplenum = None
        self.last_n = deque()
        self.chunks = 0
        self.level_changed = False
        self.last_t = None

    def metadata(self, key, value):
        if key == srd.SRD_CONF_SAMPLERATE:
            self.samplerate = value

    def start(self):
        self.out_ann = self.register(srd.OUTPUT_ANN)
        self.edge = self.options['edge']

    def decode(self):
        if not self.samplerate:
            raise SamplerateError('Cannot decode without samplerate.')
        while True:
            if self.edge == 'rising':
                pin = self.wait({0: 'r'})
            elif self.edge == 'falling':
                pin = self.wait({0: 'f'})
            else:
                pin = self.wait({0: 'e'})

            if not self.last_samplenum:
                self.last_samplenum = self.samplenum
                continue
            samples = self.samplenum - self.last_samplenum
            t = samples / self.samplerate

            if t > 0:
                self.last_n.append(t)
            if len(self.last_n) > self.options['avg_period']:
                self.last_n.popleft()

            self.put(self.last_samplenum, self.samplenum, self.out_ann,
                     [0, [normalize_time(t)]])
            if self.options['avg_period'] > 0:
                self.put(self.last_samplenum, self.samplenum, self.out_ann,
                         [1, [normalize_time(sum(self.last_n) / len(self.last_n))]])
            if self.last_t and self.options['delta'] == 'yes':
                self.put(self.last_samplenum, self.samplenum, self.out_ann,
                         [2, [normalize_time(t - self.last_t)]])
            if self.last_t and self.options['conv_a'] != 0:
                self.put(self.last_samplenum, self.samplenum, self.out_ann,
                         [3, ["%f" % (t*self.options['conv_a'] + self.options['conv_b'])]])

            self.last_t = t
            self.last_samplenum = self.samplenum
