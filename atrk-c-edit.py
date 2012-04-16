#!/usr/bin/env python --
# -*- coding: utf-8 -*-
#
#    Autotracker-C - the even more ultimate audio experience
#    (C) Ben "GreaseMonkey" Russell, 2010
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.

import sys, struct, random
import math

# we'll do major as our base this time
if random.random() < 0.4: # minor
	BASE_SCALE = [ 0, 2, 3, 5, 7, 8, 10 ]
	BASE_ISCALE = [ 0, 0, 1, 2, 2, 3, 3, 4, 5, 5, 6, 6 ]
else: # major
	BASE_SCALE = [ 0, 2, 4, 5, 7, 9, 11 ]
	BASE_ISCALE = [ 0, 0, 1, 1, 2, 3, 3, 4, 4, 5, 5, 6 ]
BASE_ICHORDS = [[] for i in xrange(12)]
BASE_IBASS = [[] for i in xrange(12)]
for i in [0,3,4,5]:
	for j in xrange(3):
		BASE_IBASS[BASE_SCALE[(i+j*2)%7]].append(BASE_SCALE[i])
for i in xrange(6):
	for j in xrange(3):
		BASE_ICHORDS[BASE_SCALE[(i+j*2)%7]].append(BASE_SCALE[i])

# strategies we can use
STRAT_CHORUS = 1
STRAT_VERSE = 2
STRAT_PRECHORUS = 3
STRAT_INTERLUDE = 4 # minor <-> major pretty much
STRAT_INTRO = 5 # must be done after doing the chorus
STRAT_OUTRO = 6

STRAT_FLAGS_RELATE = 0x100 # attempt to relate to reference
STRAT_FLAGS_START = 0x200 # start with base note
STRAT_FLAGS_END = 0x400 # end with base note and cadence
STRAT_FLAGS_TRANSITION = 0x800 # aim for base note after end and cadence
STRAT_FLAGS_COPY = 0x1000 # just copy the pattern data
STRAT_FLAGS_COMPOTRANSPOSE = 0x2000 # DON'T DO ANYTHING ELSE
STRAT_FLAGS_FADEOUT = 0x4000

# stages are 16 rows long
# there are 4 stages per 64-row pattern
# stretches are 1 64-row pattern long

def relnote(n, a):
	kn = BASE_ISCALE[(n+120)%12] + (n/12)*7
	kn += a
	return BASE_SCALE[(kn+70)%7] + (kn/7)*12

def nearinate(ln, n):
	if n >= 12:
		if abs(n-12-ln) < abs(n-ln):
			return n-12
		else:
			return n
	else:
		if abs(n+12-ln) < abs(n-ln):
			return n+12
		else:
			return n
	
class Depender:
	def __init__(self, sng, parent):
		self.parent = parent
		self.sng = sng
		if parent:
			parent.add_dep(self)
		self.deps = []
	
	# add dependency
	def add_dep(self, dep):
		self.deps.append(dep)
	
	# delegate stuff to your children
	def delegate(self):
		for d in self.deps:
			d.delegate()
			d.depend()
	
	# delegate spice to your children
	# this does the actual pattern writing
	def delegate_spice(self, pat, stage):
		for d in self.deps:
			d.delegate_spice(pat, stage)
		
		self.spice(pat, stage)
	
	###################################
	# v OVERRIDE THESE METHODS HERE v #
	###################################
	
	# make your mind up on the matter
	def initiate(self):
		pass
	
	# make children repeat strat
	def repeat(self):
		pass
	
	# depend on parent decision
	def depend(self):
		pass
	
	# make your piece awesome
	def spice(self, pat, stage):
		pass

class LeadInstrument(Depender):
	def __init__(self, sng, parent):
		Depender.__init__(self, sng, parent)
		self.ch = sng.alloc(1, True)
		self.last_note = 0
		self.steal_note = False
	
	def spice(self, pat, stage):
		n1 = self.sng.lead_data[stage]
		n2 = self.sng.lead_data[stage+1] if stage+1 < len(self.sng.lead_data) else n1
		base = (stage&3)*16
		if (pat.strat&255) == STRAT_OUTRO:
			if (pat.strat & STRAT_FLAGS_START) and base == 0:
				pat.data[base][self.ch][0] = 254 # note cut
			
			return
		elif (pat.strat&255) == STRAT_INTRO:
			return
		
		if not self.steal_note:
			pat.data[base][self.ch][0] = n1+60
			pat.data[base][self.ch][1] = 1
		
		last_steal = self.steal_note
		
		self.steal_note = random.random() < 0.6
		
		#print n1,n2
		
		stealstep = random.randint(1,2)
		if pat.strat & STRAT_FLAGS_END and (stage & 3) == 3:
			self.steal_note = False
		else:
			noteseq = []
			
			r = random.randint(1,1)
			if r == 1: # steping two notes just before n2
				# pick either one for equal
				if n2 > n1 or (n2 == n1 and random.random() < 0.5):
					noteseq.append(relnote(n2,-2))
					noteseq.append(relnote(n2,-1))
				else:
					noteseq.append(relnote(n2,2))
					noteseq.append(relnote(n2,1))
		
			beatseq = []
			lbs = 2
			tgt = 8-len(noteseq)
			if last_steal:
				tgt -= stealstep
			
			for i in xrange(len(noteseq)):
				lbs = random.randint(lbs,tgt)
				tgt += 1
				beatseq.append(2*lbs)
			
			for i in xrange(len(noteseq)):
				pat.data[base+beatseq[i]][self.ch][0] = noteseq[i]+60
				pat.data[base+beatseq[i]][self.ch][1] = 1
		
		if self.steal_note:
			
			pat.data[base+16-stealstep*2][self.ch][0] = n2+60
			pat.data[base+16-stealstep*2][self.ch][1] = 1
		
	
	def initiate(self):
		note = 0
		
		if (self.sng.strat&255) == STRAT_INTERLUDE:
			note = BASE_SCALE[4] if (self.sng.strat & STRAT_FLAGS_END) and self.sng.stretch_pos == 3 else BASE_SCALE[5]
		elif (self.sng.strat&255) == STRAT_PRECHORUS:
			note = BASE_SCALE[4] if (self.sng.strat & STRAT_FLAGS_END) and self.sng.stretch_pos == 3 else BASE_SCALE[1]
		
		if (self.sng.strat & STRAT_FLAGS_START) and self.sng.stretch_pos == 0:
			self.last_note = 0
			pass
		elif (self.sng.strat & STRAT_FLAGS_END) and self.sng.stretch_pos == 3:
			pass
		elif (self.sng.strat & STRAT_FLAGS_RELATE) and self.sng.ref != -1:
			note = random.choice(BASE_ICHORDS[(self.sng.bass_data[self.sng.ref*4+self.sng.stretch_pos]+120)%12])
		else:
			note = random.choice(BASE_SCALE[:-1]) # don't use 7 here
		
		note = nearinate(self.last_note,note)
		
		self.sng.lead_data.append(note)
		self.last_note = note
		self.delegate()

class BassInstrument(Depender):
	def __init__(self, sng, parent):
		Depender.__init__(self, sng, parent)
		self.ch = sng.alloc(1, True)
		self.last_note = 0
	
	def spice(self, pat, stage):
		n = self.sng.bass_data[stage]
		base = (stage&3)*16
		
		for i in xrange(0,16,2):
			pat.data[base+i][self.ch][0] = n+60
			pat.data[base+i][self.ch][1] = 2
	
	def depend(self):
		note = 0
		
		if (self.sng.strat&255) == STRAT_INTERLUDE:
			note = BASE_SCALE[4] if (self.sng.strat & STRAT_FLAGS_END) and self.sng.stretch_pos == 3 else BASE_SCALE[5]
		elif (self.sng.strat&255) == STRAT_PRECHORUS:
			note = BASE_SCALE[4] if (self.sng.strat & STRAT_FLAGS_END) and self.sng.stretch_pos == 3 else BASE_SCALE[1]
		
		if (self.sng.strat & STRAT_FLAGS_START) and self.sng.stretch_pos == 0:
			pass
		elif (self.sng.strat & STRAT_FLAGS_END) and self.sng.stretch_pos == 3:
			pass
		elif (self.sng.strat & STRAT_FLAGS_RELATE):
			note = self.sng.bass_data[self.sng.ref*4+self.sng.stretch_pos]
		else:
			note = random.choice(BASE_IBASS[self.sng.lead_data[-1]%12])
		
		if (self.sng.strat&255) == STRAT_PRECHORUS and note == 0:
			note = BASE_SCALE[5]
		
		note = nearinate(12,note+12)-12
		self.sng.bass_data.append(note)
		self.last_note = note
	
	def initiate(self):
		raise Exception("BassInstrument not meant to initiate")

class DrumInstrument(Depender):
	def __init__(self, sng, parent):
		Depender.__init__(self, sng, parent)
		self.ch = sng.alloc(3, False)
		self.skip_kick = False
	
	def spice(self, pat, stage):
		rbase = (stage&3)*16
		
		note = 60
		
		for q in xrange(2):
			base = rbase + q*8
			prekick = (random.random() < 0.5)
			
			if not self.skip_kick:
				pat.data[base][self.ch+1][0] = note
				pat.data[base][self.ch+1][1] = 4
			
			if prekick:
				pat.data[base+2][self.ch+1][0] = note
				pat.data[base+2][self.ch+1][1] = 4
			
			pat.data[base+4][self.ch+2][0] = note
			pat.data[base+4][self.ch+2][1] = 5
			
			for i in xrange(0,8,2):
				pat.data[base+i][self.ch][0] = note
				pat.data[base+i][self.ch][1] = 3
				if i%4 == 2:
					pat.data[base+i][self.ch][2] = 30
			
			if (pat.strat & STRAT_FLAGS_START) and base == 0:
				prekick = False
			elif (pat.strat & STRAT_FLAGS_END) and base == 56:
				self.skip_kick = False
				for i in xrange(2,8,2):
					pat.data[base+i][self.ch+2][0] = note
					pat.data[base+i][self.ch+2][1] = 5
			elif (pat.strat & STRAT_FLAGS_RELATE): # blatant copy
				opat = self.sng.refpat(pat.ref)
				for i in xrange(8):
					for j in xrange(3):
						pat.data[base+i][self.ch+j] = opat.data[base+i][self.ch+j][:]
				continue
			
			self.skip_kick = (random.random() < 0.4)
			
			if self.skip_kick:
				pat.data[base+6][self.ch+1][0] = note
				pat.data[base+6][self.ch+1][1] = 4
	
	def depend(self):
		# drums only happen in spice
		pass
	
	def initiate(self):
		raise Exception("DrumInstrument not meant to initiate")

class ChordInstrument(Depender):
	def __init__(self, sng, parent):
		Depender.__init__(self, sng, parent)
		self.ch = sng.alloc(3, True)
		self.last_note = None
	
	def spice(self, pat, stage):
		nb = (self.sng.bass_data[stage]+120)%12
		n1 = (self.sng.chord_data[stage]+120)%12
		n2 = (relnote(n1,2)+120)%12
		n3 = (relnote(n1,4)+120)%12
		base = (stage&3)*16
		
		if base == 0:
			self.last_note = None
		
		if n1 != self.last_note:
			pat.data[base][self.ch][0] = nb+60
			pat.data[base][self.ch][1] = 6
			
			if n2 == nb:
				pat.data[base][self.ch][0] = n2+60
				pat.data[base][self.ch][1] = 6
				pat.data[base][self.ch+1][0] = n3+60
				pat.data[base][self.ch+1][1] = 6
				pat.data[base][self.ch+2][0] = n1+60+12
				pat.data[base][self.ch+2][1] = 6
			elif n3 == nb:
				pat.data[base][self.ch][0] = n3+60
				pat.data[base][self.ch][1] = 6
				pat.data[base][self.ch+1][0] = n1+60+12
				pat.data[base][self.ch+1][1] = 6
				pat.data[base][self.ch+2][0] = n2+60+12
				pat.data[base][self.ch+2][1] = 6
			else:
				pat.data[base][self.ch][0] = n1+60
				pat.data[base][self.ch][1] = 6
				pat.data[base][self.ch+1][0] = n2+60
				pat.data[base][self.ch+1][1] = 6
				pat.data[base][self.ch+2][0] = n3+60
				pat.data[base][self.ch+2][1] = 6
		
		self.last_note = n1
	
	def depend(self):
		note = 0
		
		if (self.sng.strat&255) == STRAT_INTERLUDE:
			note = 7 if (self.sng.strat & STRAT_FLAGS_END) and self.sng.stretch_pos == 3 else 9
		elif (self.sng.strat&255) == STRAT_PRECHORUS:
			note = 7 if (self.sng.strat & STRAT_FLAGS_END) and self.sng.stretch_pos == 3 else 2
		
		if (self.sng.strat & STRAT_FLAGS_START) and self.sng.stretch_pos == 0:
			pass
		elif (self.sng.strat & STRAT_FLAGS_END) and self.sng.stretch_pos == 3:
			pass
		elif (self.sng.strat & STRAT_FLAGS_RELATE):
			note = self.sng.chord_data[self.sng.ref*4+self.sng.stretch_pos]
		else:
			note = random.choice(BASE_ICHORDS[self.sng.bass_data[-1]%12])
		
		if (self.sng.strat&255) == STRAT_PRECHORUS and note == 0:
			note = 9
		
		note = nearinate(12,note+12)-12
		
		self.sng.chord_data.append(note)
	
	def initiate(self):
		raise Exception("ChordInstrument not meant to initiate")

class FadeoutEffect(Depender):
	def __init__(self, sng, parent):
		Depender.__init__(self, sng, parent)
		self.ch = sng.alloc(1, False)
		self.fade_len = 0
	
	def spice(self, pat, stage):
		base = (stage&3)*16
		if (pat.strat&255) == STRAT_INTRO and (pat.strat & STRAT_FLAGS_START) and (stage&3) == 0:
			pat.data[0][self.ch][3] = 22
			pat.data[0][self.ch][4] = 0x80
		elif (pat.strat&255) == STRAT_OUTRO:
			for i in xrange(0,16,self.sng.stretch_len/2):
				pat.data[base+i][self.ch][3] = 23
				pat.data[base+i][self.ch][4] = 0xF1
	
	def depend(self):
		if (self.sng.strat&255) == STRAT_OUTRO:
			self.fade_len = self.sng.stretch_len
		
	
	def initiate(self):
		raise Exception("FadeoutEffect not meant to initiate")

class SwingEffect(Depender):
	def __init__(self, sng, parent):
		Depender.__init__(self, sng, parent)
		self.ch = sng.alloc(1, False)
		self.fade_len = 0
		self.swing_str = random.randint(-1,2)
		if self.swing_str <= 0:
			self.swing_str = 0
	
	def spice(self, pat, stage):
		base = (stage&3)*16
		if self.swing_str == 1:
			for i in xrange(0,16,4):
				pat.data[base+i][self.ch][3] = 1
				pat.data[base+i][self.ch][4] = 5
				pat.data[base+i+2][self.ch][3] = 1
				pat.data[base+i+2][self.ch][4] = 3
		elif self.swing_str == 2:
			for i in xrange(0,16,4):
				pat.data[base+i][self.ch][3] = 1
				pat.data[base+i][self.ch][4] = 6
				pat.data[base+i+2][self.ch][3] = 1
				pat.data[base+i+2][self.ch][4] = 3
	
	def depend(self):
		pass
	
	def initiate(self):
		raise Exception("SwingEffect not meant to initiate")

class Pattern:
	def __init__(self, rows, strat, ref):
		self.rows = rows
		self.strat = strat
		self.ref = ref
		self.data = [[[-1,-1,-1,-1,0] for i in xrange(64)] for i in xrange(rows)]
	
	def save(self, fp):
		# don't bother packing well, you'll need to add your samples in -GM
		odat = []
		
		for l in self.data:
			for ch in xrange(64):
				m = 0x00
				
				if l[ch][0] != -1:
					m |= 0x01
				if l[ch][1] != -1:
					m |= 0x02
				if l[ch][2] != -1:
					m |= 0x04
				if l[ch][3] != -1:
					m |= 0x08
				
				odat.append(0x80|(ch+1))
				odat.append(m)
				if m & 0x01:
					odat.append(l[ch][0])
				if m & 0x02:
					odat.append(l[ch][1])
				if m & 0x04:
					odat.append(l[ch][2])
				if m & 0x08:
					odat.append(l[ch][3])
					odat.append(l[ch][4])
			odat.append(0)
		
		fp.write(struct.pack("<HHI",len(odat),self.rows,0))
		fp.write(''.join(chr(v) for v in odat))

class Song:
	def __init__(self):
		self.orders = []
		self.samples = self.gen_samples()
		self.patterns = []
		self.pat_chorus = []
		self.pat_chorus_base = 0
		self.pat_chorus_ord = 0
		self.chnbase = 0
		self.chn_tonal = [False for i in xrange(64)]
		
		self.lead_data = []
		self.beat_data = []
		self.bass_data = []
		self.chord_data = []
		
		self.key = random.randint(-6,6) # 0 == (major ? C : Am)
		self.mode = 0 # 0 == major, -3 = minor
		self.strat = 0
		self.ref = 0
		
		self.stretch_len = 0
		self.stretch_pos = 0
		
		# OK, let's rock
		lead = LeadInstrument(self, None)
		bass = BassInstrument(self, lead)
		drum = DrumInstrument(self, lead)
		chords = ChordInstrument(self, bass)
		fx_fadeout = FadeoutEffect(self, lead)
		fx_swing = SwingEffect(self, lead)
		self.root = lead
		
		self.epictronise()
	
	def fakesin(self,v):
		v = v % math.pi*2
		return -0.5 if v < math.pi else 0.5
	
	def saw(self,v,d):
		return ((float(v)/float(d)) % 1.0)*2.0-1.0
	
	def gen_samples(self):
		l = []
		
		# sample 1: lead: square
		l.append(([(-60 if i%256 < 128 else 60)+(-60 if i%255 < 128 else 60) for i in xrange(256*255)],8363*8,True))
		
		# sample 2: bass: sawtooth
		l.append(([(((i%64)-32)*180*(i**2))/(64*((64*50)**2)) for i in xrange(64*50)][::-1],8363,True))
		
		# sample 3: hihat
		q = []
		for i in xrange(650):
			q = [(random.randint(-1,1)*120*i*i)/(650*650)] + q
		l.append((q,8134*4,False))
		
		# sample 4: kick
		q = []
		for i in xrange(4000):
			q = [int(120*self.fakesin(i*i*i*math.pi*2.0*4/(4000.0**3)))] + q
		l.append((q,8134*4,False))
		
		# sample 5: snare
		q = []
		for i in xrange(650*4):
			q = [(random.randint(-1,1)*120*i*i)/(650*650*4*4)] + q
		l.append((q,8134*2,False))
		
		# sample 6: chord: hypersaw
		# NOTE: this is not a proper hypersaw as it doesn't distort enough.
		#q = []
		#for i in xrange(8363*16):
		#	q.append(int(15*(
		#		self.saw(i*2048+12345,8363*16)*4
		#		+ self.saw(i*1024+67890,8363*16)*2
		#		+ self.saw(i*512+2467,8363*16)*1
		#		+ self.saw(i*4096+5437,8363*16)*1
		#	)))
		# decided to change the waveform.
		# it's now a triangle wave.
		q = [((i-32)*120)/64 for i in xrange(64)]
		l.append((q+q[::-1],8363*4,True))
		
		return l
	
	def refpat(self, ref):
		return self.patterns[self.orders[ref]]
	
	def gen_pat(self, strat, ref = -1):
		p = Pattern(64, strat, ref)
		
		self.strat = strat
		self.ref = ref
		
		for i in xrange(4):
			self.stretch_pos = i
			self.root.initiate()
		
		self.orders.append(len(self.patterns))
		self.patterns.append(p)
		if (strat&255) == STRAT_CHORUS and len(self.pat_chorus) < self.stretch_len:
			self.pat_chorus.append(p)
	
	def gen_pat_round(self, strat):
		choref = self.pat_chorus_ord
		if (strat&255) == STRAT_CHORUS:
			if self.pat_chorus and not (strat & STRAT_FLAGS_COPY):
				print "rep", self.pat_chorus_base, self.pat_chorus_ord, len(self.orders)
				
				# just tweak the orderlist and sync the song data
				for i in xrange(len(self.pat_chorus)):
					self.orders.append(self.pat_chorus_base+i)
					for j in xrange(4):
						for q in [self.lead_data, self.chord_data, self.bass_data, self.beat_data]:
							if q:
								q.append(q[(self.pat_chorus_ord+i)*4+j])
				return
			else:
				self.pat_chorus = []
				self.pat_chorus_ord = len(self.orders)
				self.pat_chorus_base = len(self.patterns)
		
		for i in xrange(self.stretch_len):
			ts = strat
			ref = -1
			
			if i == 0:
				ts |= STRAT_FLAGS_START
			else:
				k = i
				ref = 1
				while k and not k&1:
					ref <<= 1
					k >>= 1
				
				ref = len(self.orders)-ref
				
				ts |= STRAT_FLAGS_RELATE
			
			if strat & STRAT_FLAGS_COMPOTRANSPOSE:
				if (strat&255) == STRAT_CHORUS:
					ref = choref+i
				elif (strat&255) == STRAT_OUTRO:
					ref = len(self.orders)-self.stretch_len
			
			if (strat&255) == STRAT_OUTRO:
				ref = len(self.orders)-1
				ts |= STRAT_FLAGS_RELATE
			elif i == self.stretch_len-1:
				ts |= STRAT_FLAGS_END
			
			self.gen_pat(ts, ref)
	
	def epictronise(self):
		self.strat_list = [
			STRAT_INTRO,
			STRAT_CHORUS,
			STRAT_VERSE, STRAT_PRECHORUS, STRAT_CHORUS,
			STRAT_VERSE, STRAT_PRECHORUS, STRAT_INTERLUDE, STRAT_CHORUS,
			STRAT_CHORUS|STRAT_FLAGS_COPY|STRAT_FLAGS_COMPOTRANSPOSE,
			STRAT_VERSE, STRAT_PRECHORUS, STRAT_CHORUS,
			STRAT_CHORUS|STRAT_FLAGS_COPY|STRAT_FLAGS_COMPOTRANSPOSE,
			STRAT_OUTRO
		]
		
		for strat in self.strat_list:
			self.stretch_len = random.choice([2,4])
			if (strat&255) == STRAT_INTRO:
				self.stretch_len = 2
			elif (strat&255) == STRAT_CHORUS:
				self.stretch_len = 2
			elif (strat&255) == STRAT_OUTRO:
				self.stretch_len = 4
			
			
			self.curpat = None
			
			self.gen_pat_round(strat)
		
		l = []
		for i in xrange(len(self.orders)):
			if self.orders[i] in l:
				continue
			
			l.append(self.orders[i])
			for j in xrange(4):
				self.root.delegate_spice(self.refpat(i), i*4+j)
		
		last_was_transpose = False
		for p in self.patterns:
			for r in xrange(p.rows):
				for ch in xrange(64):
					if self.chn_tonal[ch] and p.data[r][ch][0] != -1 and p.data[r][ch][0] < 120:
						p.data[r][ch][0] += self.key
			
			if p.strat & STRAT_FLAGS_COPY:
				op = self.refpat(p.ref)
				for r in xrange(p.rows):
					for ch in xrange(64):
						p.data[r][ch] = op.data[r][ch][:]
			
			if p.strat & STRAT_FLAGS_COMPOTRANSPOSE:
				for r in xrange(p.rows):
					for ch in xrange(64):
						if self.chn_tonal[ch] and p.data[r][ch][0] != -1 and p.data[r][ch][0] < 120:
							p.data[r][ch][0] += 2
				
				if not last_was_transpose:
					self.key += 2
				
				last_was_transpose = True
			else:
				last_was_transpose = False
	
	def alloc(self, count, tonal):
		b = self.chnbase
		self.chnbase += count
		for i in xrange(b,self.chnbase,1):
			self.chn_tonal[i] = tonal
		return b
	
	def save(self, fname):
		fp = open(fname, "wb")
		fp.write("IMPM AutoTracker C Module :D \x00")
		fp.write(struct.pack("<HHHHH",0x1004,len(self.orders)+1,0,len(self.samples),len(self.patterns)))
		fp.write(struct.pack("<HHHH",0x0216,0x0200,0x0019,0x0000))
		fp.write(struct.pack("<BBBBBB",128,48,4,125,128,0))
		fp.write(struct.pack("<HII",0,0,0))
		fp.write("\x20"*64)
		fp.write("\x40"*64)
		fp.write(''.join(chr(v) for v in self.orders)+"\xFF")
		patroot = fp.tell()
		fp.write("\x00"*4*(len(self.samples)+len(self.patterns)))
		
		# do it ChibiTracker-style
		for dat,frq,lpd in self.samples:
			t = fp.tell()
			fp.write("IMPSAUTOTRACKERC\x00")
			fp.write(struct.pack("<BBB",64,0x11 if lpd else 0x01,64))
			fp.write("Autotracker C sample     \x00")
			fp.write(struct.pack("<BB",0x01,0x00))
			fp.write(struct.pack("<IIIIIII",len(dat),0,len(dat),frq,0,0,t+0x50))
			fp.write(struct.pack("<BBBB",0x00,0x00,0x00,0x00))
			fp.write(''.join(chr(255&v) for v in dat))
			nt = fp.tell()
			fp.seek(patroot)
			fp.write(struct.pack("<I",t))
			patroot = fp.tell()
			fp.seek(nt)
		
		for p in self.patterns:
			t = fp.tell()
			p.save(fp)
			nt = fp.tell()
			fp.seek(patroot)
			fp.write(struct.pack("<I",t))
			patroot = fp.tell()
			fp.seek(nt)
		
		fp.close()

Song().save("dump-c.it")
