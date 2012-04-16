#!/usr/bin/env python2 --
# -*- coding: utf-8 -*-
#
# munch.py - The only .it packer you'll need (eventually)
# by Ben "GreaseMonkey" Russell, 2011 - PUBLIC DOMAIN
#
# ok the hype about IT214 compression was getting out of hand.
# it finally decompresses AND compresses samples correctly.
# i believe all IT214-related bugs have been ironed out with a chainsaw.
# unfortunately, nothing supports compressed stereo... HMM I WONDER WHY
# (IT seems to take it fine, albeit w/o a right channel)
# 
# with that said, thanks to xaimus for making thor-ainor.it,
# it was a really good compressor test and exposed a bug in the 16-bit compressor/decompressor.
#
# UPDATE: At the suggestion of Storlek, this now does IT215. Enjoy.
#
# UPDATE: Now has some slight optimisation in the comparisons department.
# In this case, this does the arranging for stereo.it in under a second.
#
# UPDATE: compressed stereo samples follow the XMPlay scheme.
# Also, fillin has been updated so it's actually useful.
# TODO: get an optimal algorithm.

# ok, this usually fares better than IT itself for some weird reason.
# Jeffery Lim, take note of this.
# in fact, you're allowed to steal my algorithm. it's public domain, after all.
# so yeah, this is now SET. time to listen to this COMP304 lecture more intently.
DECOMPRESS_IT214 = True

# however, if you don't have IT, this actually works. i think.
# if it doesn't, you might want to turn it off.
COMPRESS_IT214 = True

# this only makes sense if you have COMPRESS_IT214 enabled.
# DOUBLE DELTAS LOLS
COMPRESS_IT215 = True

# this only makes sense if you have COMPRESS_IT214 enabled.
# WARNING: not supported in most players!
# TRIPLE DELTAS LOLS
COMPRESS_BYTEDELTA = False

# de-stereos samples.
# use this if IT hates you.
STEREO_TAKELEFT = True

# types are "recursive crater", "abstract fillin", "fillin", and "crater".
IT214_ALGO_SELECT = "recursive crater"

# this should hopefully speed up what's been done.
IT214_ALGO_RECURSIVE_CRATER = IT214_ALGO_SELECT == "recursive crater"

# this has been an experiment and is currently very inefficient. don't use it.
IT214_ALGO_ABSTRACT_FILLIN = IT214_ALGO_SELECT == "abstract fillin"

# if you want to, try this algorithm. about half the time, it beats crater.
IT214_ALGO_FILLIN = IT214_ALGO_SELECT == "fillin"

import sys, struct
import heapq

# <del><del>O(n^2) comparison. IT'S EVERYWHERE.</del>
# THIS NOW USES KNUTH-MORRIS-PRATT / O(n). HAVE A NICE DAY.</del>
# OK, back to O(n^2). BUT WITH SOME OPTIMISATION THING
class ITFloater:
	#kmp_search_tree = None
	first_instance_map = None
	none_instance_map = None
	
	def compare_floaters_part(self, other, offs):
		for i in xrange(min(len(other.mask),len(self.mask)-offs)):
			m1 = self.mask[offs+i]
			m2 = other.mask[i]
			if m1 == None or m2 == None:
				continue
			if m1 != m2:
				return False
			if m1 == -1:
				return False
		return True
	
	def compare_floaters(self, other, offs):
		# mask[0] is neither -1 nor None for self or other
		# how's that for a mouthful of logical contractions
		p = self.none_instance_map[:]
		q = self.first_instance_map[other.mask[0]][:]
		qoffs = 0
		while p or q:
			if p and ((not q) or p[0] < q[0]):
				qoffs = heapq.heappop(p)
			else:
				qoffs = heapq.heappop(q)
			
			if qoffs < offs:
				continue
			offs = qoffs
			
			if self.compare_floaters_part(other, offs):
				return offs
		
		return len(self.mask)
	
	def calculate_first_instance_map(self, start, length):
		self.first_instance_map = [[] for i in xrange(256)]
		self.none_instance_map = []
		for i in xrange(start, length, 1):
			v = self.mask[i]
			
			if v == None:
				self.none_instance_map.append(i)
			elif v != -1:
				self.first_instance_map[v].append(i)
		
		for v in xrange(256):
			heapq.heapify(self.first_instance_map[v])
		
		heapq.heapify(self.none_instance_map)
	
	# using wikipedia's def^n of this.
	def compare_floaters_kmp(self, other, offs):
		if other.kmp_search_tree == None:
			other.build_kmp_search_tree()
		
		t = other.kmp_search_tree
		
		#print t
		
		# algo start
		m = offs
		i = 0
		
		s = self.mask
		w = other.mask
		while m+i < len(s):
			#print i,len(w),m+i,len(s)
			# both None checks are necessary for this to pack well.
			if w[i] == s[m+i] or s[m+i] == None or w[i] == None:
				#print "match",m,i
				if i == len(w)-1:
					return m
				i += 1
			else:
				#print "skip",m,i,t[i]
				m += i - t[i]
				if t[i] > -1:
					i = t[i]
				else:
					i = 0
		
		# this is where it varies.
		#return len(s)
		return m
	
	# using wikipedia's def^n of this.
	# THERE SHOULDN'T BE ANY STRINGS LESS THAN 2 BYTES HERE.
	# (i.e. DON'T USE 1-BYTE SAMPLES)
	def build_kmp_search_tree(self):
		pos = 2
		cnd = 0
		self.kmp_search_tree = [-1,0] + [0 for i in xrange(len(self.mask))]
		
		while pos < len(self.mask):
			# first case: the substring continues
			# NOTE: the first None check made a file larger than it should be.
			# the second actually produces incorrect data and is caught by the AssertionError.
			if self.mask[pos - 1] == self.mask[cnd] or self.mask[cnd] == None:# or self.mask[pos - 1] == None:
				cnd += 1
				self.kmp_search_tree[pos] = cnd
				pos += 1
			
			# second case: it doesn't, but we can fall back
			elif cnd > 0:
				cnd = self.kmp_search_tree[cnd]
			
			# third case: we have run out of candidates.  Note cnd = 0
			else:
				cnd = 0
				pos += 1



# TODO unravel patterns and repack them
class ITPattern(ITFloater):
	def __init__(self, fp):
		patlen, self.rows, _ = struct.unpack("<HHI",fp.read(8))
		# Ignore pattern length. Very occasionally, patterns are >= 64KB.
		# Plus there's plenty of checks and balances in everything ever.
		# Not sure about IT, sadly.
		
		# We'll calculate to check if it's correct, though.
		pdroot = fp.tell()
		
		self.data = [[[253,0,255,0,0] for i in xrange(64)] for r in xrange(self.rows)]
		
		# TODO? check what the defaults are?
		lmask = [-1 for i in xrange(64)]
		ldata = [[-1,-1,-1,-1,-1] for i in xrange(64)]
		
		for r in xrange(self.rows):
			while True:
				ch = ord(fp.read(1))
				if ch == 0:
					break
				elif ch & 0x80:
					ch -= 0x81
					lmask[ch] = ord(fp.read(1))
				else:
					ch -= 0x01
				
				if lmask[ch] & 0x01:
					ldata[ch][0] = ord(fp.read(1))
				if lmask[ch] & 0x02:
					ldata[ch][1] = ord(fp.read(1))
				if lmask[ch] & 0x04:
					ldata[ch][2] = ord(fp.read(1))
				if lmask[ch] & 0x08:
					ldata[ch][3] = ord(fp.read(1))
					ldata[ch][4] = ord(fp.read(1))
				
				if lmask[ch] & 0x11:
					self.data[r][ch][0] = ldata[ch][0]
				if lmask[ch] & 0x22:
					self.data[r][ch][1] = ldata[ch][1]
				if lmask[ch] & 0x44:
					self.data[r][ch][2] = ldata[ch][2]
				if lmask[ch] & 0x88:
					self.data[r][ch][3] = ldata[ch][3]
					self.data[r][ch][4] = ldata[ch][4]
		
		self.currently_used = False
	
	def use(self, module):
		if not self.currently_used:
			lins = [0 for i in xrange(64)]
			for row in self.data:
				for chidx in xrange(64):
					chn = row[chidx]
					if chn[0] <= 119:
						module.chn_has_sound[chidx] = True
					if chn[1] != 0:
						lins[chidx] = chn[1]
						if module.flags & 4:
							if chn[1] != 0:
								if chn[1]-1 < len(module.inslist):
									module.make_use_of(module.inslist[chn[1]-1],"instrument",chn[1]-1)
						else:
							if chn[1] != 0:
								if chn[1]-1 < len(module.smplist):
									module.make_use_of(module.smplist[chn[1]-1],"sample",chn[1]-1)
					
					if module.flags & 4:
						if lins[chidx] != 0:
							if chn[0] < 120:
								if lins[chidx]-1 < len(module.smplist):
									module.inslist[lins[chidx]-1].patuse(module,chn[0])
		
		self.currently_used = True
	
	def remap_smpins(self, smpinsmap):
		for row in self.data:
			for chidx in xrange(64):
				chn = row[chidx]
				if chn[1] != 0:
					#print chn[1],smpinsmap[chn[1]-1]+1
					if chn[1]-1 in smpinsmap:
						chn[1] = smpinsmap[chn[1]-1]+1
					else:
						chn[1] = 99
	
	def pack(self):
		packdata = []
		
		lmask = [-1 for i in xrange(64)]
		ldata = [[-1,-1,-1,-1,-1] for i in xrange(64)]
		
		print "Packing pattern..."
		for row in self.data:
			for ch in xrange(64):
				cell = row[ch]
				# TODO delegate mask calc to own method
				mask = 0
				if cell[0] != 253:
					if cell[0] == ldata[ch][0]:
						mask |= 0x10
					else:
						mask |= 0x01
						ldata[ch][0] = cell[0]
				if cell[1] != 0:
					if cell[1] == ldata[ch][1]:
						mask |= 0x20
					else:
						mask |= 0x02
						ldata[ch][1] = cell[1]
				if cell[2] != 255:
					if cell[2] == ldata[ch][2]:
						mask |= 0x40
					else:
						mask |= 0x04
						ldata[ch][2] = cell[2]
				if cell[3] != 0 or cell[4] != 0:
					if cell[3] == ldata[ch][3] and cell[4] == ldata[ch][4]:
						mask |= 0x80
					else:
						mask |= 0x08
						ldata[ch][3] = cell[3]
						ldata[ch][4] = cell[4]
				
				if mask:
					if lmask[ch] == mask:
						packdata.append(ch+0x01)
					else:
						packdata.append(ch+0x81)
						packdata.append(mask)
						lmask[ch] = mask
					
					if mask & 0x01:
						packdata.append(cell[0])
					if mask & 0x02:
						packdata.append(cell[1])
					if mask & 0x04:
						packdata.append(cell[2])
					if mask & 0x08:
						packdata.append(cell[3])
						packdata.append(cell[4])
			
			packdata.append(0)
		
		if len(packdata) > 0xFFFF:
			print "WARNING: Pattern length > 65535 bytes."
		q = struct.pack("<HH", len(packdata), self.rows)
		
		self.mask = [ord(q[0]),ord(q[1]),ord(q[2]),ord(q[3]),None,None,None,None] + packdata
	
	def optimise(self, module):
		print "Optimising pattern..."
		
		print "- checking for effects that do absolutely nothing"
		for row in self.data:
			for cell in row:
				# .xx -> .00
				if cell[3] == 0:
					cell[4] = 0
				
				# [A]00 -> .00
				if cell[3] in [1] and cell[4] == 0:
					cell[3] = 0
		
		print "- checking for unnecessary changes in voleffect/effect data"
		for ch in xrange(64):
			left = 0
			lefp = 0
			lvol = 0
			# TODO? check for (e.g. G_) Gx -> thing -> G0 -> Gx?
			#       same deal with (e.g. G__) Gxx -> thing -> G00 -> Gxx?
			# NOTE: this may screw up blatant crazy row jumpers
			#       even without that extra check O_O
			#        but more notoriously with that extra check D:
			for r in xrange(self.rows):
				cell = self.data[r][ch]
				if cell[2] != 0:
					if cell[2] >= 65 and cell[2] <= 124:
						if cell[2]%10 == 5 and (cell[2]-65)//10 == (lvol-65)//10:
							cell[2] = lvol
					if cell[2] >= 193 and cell[2] <= 212:
						if cell[2]%10 == 3 and (cell[2]-193)//10 == (lvol-193)//10:
							cell[2] = lvol
					lvol = cell[2]
				if cell[3] != 0:
					if cell[3] in [4,5,6,7,8,9,10,11,12,14,15,16,17,18,19,20,21,23,25]:
						if cell[3] == left and cell[4] == 0:
							cell[4] = lefp
					
					left = cell[3]
					lefp = cell[4]
		
		# TODO: awesome mask hacks

class IT214Exception(Exception):
	pass

class IT214ContinueException(Exception):
	pass

IT214_COMP_LOWER8  = [0,-1,-3,-7,-15,-31]
IT214_COMP_LOWER8 += [-(1<<(i-1))+4 for i in xrange(7,8+1,1)]
IT214_COMP_LOWER8 += [-128]
IT214_COMP_UPPER8  = [0, 1, 3, 7, 15, 31]
IT214_COMP_UPPER8 += [ (1<<(i-1))-5 for i in xrange(7,8+1,1)]
IT214_COMP_UPPER8 += [ 127]
IT214_COMP_LOWER16  = [0,-1,-3,-7,-15,-31]
IT214_COMP_LOWER16 += [-(1<<(i-1))+8 for i in xrange(7,16+1,1)]
IT214_COMP_LOWER16 += [-32768]
IT214_COMP_UPPER16  = [0, 1, 3, 7, 15, 31]
IT214_COMP_UPPER16 += [ (1<<(i-1))-9 for i in xrange(7,16+1,1)]
IT214_COMP_UPPER16 += [ 32767]
IT214_WIDTHCHANGESIZE = [4,5,6,7,8,9,7,8,9,10,11,12,13,14,15,16,17]

class IT214Compressor:
	def __init__(self, data, offs, length, is16, is215):
		# Probably the only IT214 compressor in the world to handle stereo samples.
		# (ok i can just about guarantee that Storlek has something)
		
		self.base_length = min(length,0x4000 if is16 else 0x8000)
		self.length = self.base_length
		
		self.packed_data = [0,0]
		self.bpos = 0
		self.brem = 8
		self.bval = 0
		self.block_length_pos = 0
		self.offs = offs
		
		self.is16 = is16
		
		self.lowertab = IT214_COMP_LOWER16 if is16 else IT214_COMP_LOWER8
		self.uppertab = IT214_COMP_UPPER16 if is16 else IT214_COMP_UPPER8
		self.dwidth = 17 if is16 else 9
		self.fetch_a = 4 if is16 else 3
		self.lower_b = -8 if is16 else -4
		
		self.data = []
		if is16:
			clamp_part = lambda x : x - 0x10000 if x >= 0x8000 else x
			self.clamp = lambda x : clamp_part(x&0xFFFF)
			self.clamp_unsigned = lambda x : (x&0xFFFF)
			for i in xrange(self.base_length):
				self.data.append(ord(data[(offs+i)*2])|(ord(data[(offs+i)*2+1])<<8))
		else:
			clamp_part = lambda x : x - 0x100 if x >= 0x80 else x
			self.clamp = lambda x : clamp_part(x&0xFF)
			self.clamp_unsigned = lambda x : (x&0xFF)
			for i in xrange(self.base_length):
				self.data.append(ord(data[(offs+i)]))
		
		self.deltafy()
		if is215:
			# DO IT AGAIN LOLOLOLOLOLOL
			self.deltafy()
		
		if IT214_ALGO_RECURSIVE_CRATER:
			self.squish_recursive()
		else:
			self.squish()
		
		self.packed_data.append(self.bval)
		self.packed_data[0] = (len(self.packed_data)-2)&0xFF
		self.packed_data[1] = (len(self.packed_data)-2)>>8
		
		if len(self.packed_data) >= 0x10002:
			raise Exception("somehow we exceeded the 16-bit counter while packing the data.")
	
	def get_length(self):
		return self.base_length
	
	def get_data(self):
		return self.packed_data
	
	def write(self, width, v):
		while width > self.brem:
			self.bval |= (v<<self.bpos)&0xFF
			width -= self.brem
			v >>= self.brem
			self.bpos = 0
			self.brem = 8
			self.packed_data.append(self.bval)
			self.bval = 0
		
		if width > 0: # uhh, this check might be redundant
			self.bval |= (v & ((1<<width)-1)) << self.bpos
			self.brem -= width
			self.bpos += width
	
	def deltafy(self):
		root = 0
		for i in xrange(self.base_length):
			root, self.data[i] = self.data[i], self.clamp(self.data[i]-root)
	
	def get_width_change_size(self, w):
		wcs = IT214_WIDTHCHANGESIZE[w-1]
		if w <= 6 and self.is16:
			wcs += 1
		
		return wcs
	
	def squish_recursive_part(self, bwt, swidth, lwidth, rwidth, width, offs, length):
		#print "width", width+1, offs, length
		if width+1 < 1:
			for i in xrange(offs,offs+length,1):
				bwt[i] = swidth
			
			return
		
		i = offs
		itarg = length+offs
		while i < itarg:
			if self.data[i] >= self.lowertab[width] and self.data[i] <= self.uppertab[width]:
				j = i
				while i < itarg and self.data[i] >= self.lowertab[width] and self.data[i] <= self.uppertab[width]:
					i += 1
				
				blklen = i-j
				
				twidth = swidth
				comparison = False
				xlwidth = lwidth if j == offs else swidth
				xrwidth = rwidth if i == itarg else swidth
				
				wcsl = self.get_width_change_size(xlwidth)
				wcss = self.get_width_change_size(swidth)
				wcsw = self.get_width_change_size(width+1)
				
				if i == self.base_length:
					keep_down = wcsl+(width+1)*blklen
					level_left = wcsl+swidth*blklen
					
					if xlwidth == swidth:
						level_left -= wcsl
					
					comparison = keep_down <= level_left
				else:
					keep_down = wcsl+(width+1)*blklen+wcsw
					level_left = wcsl+swidth*blklen+wcss
					
					if xlwidth == swidth:
						level_left -= wcsl
					if xrwidth == swidth:
						level_left -= wcss
					
					comparison = keep_down <= level_left
				
				if comparison:
					self.squish_recursive_part(bwt, width+1, xlwidth, xrwidth, width-1, j, blklen)
				else:
					self.squish_recursive_part(bwt, swidth, xlwidth, xrwidth, width-1, j, blklen)
			else:
				bwt[i] = swidth
				i += 1
	
	def squish_recursive(self):
		# initialise bit width table with initial values
		bwt = [self.dwidth for i in xrange(self.base_length)]
		
		# recurse
		self.squish_recursive_part(bwt, self.dwidth, self.dwidth, self.dwidth, self.dwidth-2, 0, self.base_length)
		
		# write
		self.squish_write(bwt)
	
	def squish(self):
		# initialise bit width table with initial values
		bwt = [self.dwidth for i in xrange(self.base_length)]
		
		if IT214_ALGO_ABSTRACT_FILLIN: # "Abstract fillin" algorithm
			# precrater then analyse
			print "building craters"
			for i in xrange(self.base_length):
				for width in xrange(self.dwidth):
					if self.data[i] >= self.lowertab[width] and self.data[i] <= self.uppertab[width]:
						bwt[i] = width+1
						break
					
					assert width != self.dwidth-1
			
			print "analysing cratery"
			l = []
			w = self.dwidth
			c = 0
			n = 0
			for v in bwt:
				if w != v:
					l.append((w,c,n))
					w = v
					c = IT214_WIDTHCHANGESIZE[w-1]
					if w <= 6 and self.is16:
						c += 1
					n = 0
				
				n += 1
			
			l.append((w,c,n))
			
			print "removing crap cratery"
			k = True
			r = 0
			while k:
				k = False
				print len(l)
				print "iteration", r+1
				r += 1
				
				i = len(l)-1
				while i >= 1:
					wl,cl,nl = l[i-1]
					wm,cm,nm = l[i]
					
					# action cost for keep / merge
					ak = wl*nl + cl + wm*nm + cm
					am = wl*(nl+nm) + cl
					act = 0 # middle -> left
					
					# target width for merge
					tw = wl
					tn = nl+nm
					
					if i == len(l)-1:
						ak -= cm
						am -= cl
					else:
						wr,cr,nr = l[i+1]
						if wr == wl:
							act = 1 # right -> middle -> left base
							am -= cl
							tn = nl+nm+nr
						else:
							amr = cl + wr*(nl+nm)
							if amr < am and wl > wm:
								act = 2 # right base -> middle
								tm = l[i+1][0]
								tw = wm
								tn = nm+nr
					
					
					if am < ak and tw > wm:
						if act == 0:
							l = l[:i-1] + [(tw,self.get_width_change_size(tw),tn)] + l[i+1:]
						elif act == 1:
							l = l[:i-1] + [(tw,self.get_width_change_size(tw),tn)] + l[i+2:]
						elif act == 2:
							l = l[:i] + [(tw,self.get_width_change_size(tw),tn)] + l[i+2:]
						else:
							raise Exception("EDOOFUS this should never happen")
						
						i -= 2
						k = True
					else:
						i -= 1
					
			
			print len(l)
			
			print "recreating bit width table"
			w,c,n = l.pop(0)
			for i in xrange(len(bwt)):
				if n == 0:
					w,c,n = l.pop(0)
				
				bwt[i] = w
				n -= 1
			
		elif IT214_ALGO_FILLIN: # "Fill in" algorithm
			# precrater then raise craters
			print "building craters"
			for i in xrange(self.base_length):
				for width in xrange(self.dwidth):
					if self.data[i] >= self.lowertab[width] and self.data[i] <= self.uppertab[width]:
						bwt[i] = width+1
						break
					
					assert width != self.dwidth-1
			
			print "raising craters"
			for width in xrange(self.dwidth):
				print "width", width+1
				beg = None
				swidth = None
				for i in xrange(self.base_length):
					if bwt[i] == width+1:
						if beg == None:
							swidth = self.dwidth
							if i > 0:
								swidth = bwt[i-1]
							beg = i
						
						if i != self.base_length-1:
							continue
						
						i += 1
					
					if beg != None:
						length = i - beg
						wcsl = IT214_WIDTHCHANGESIZE[swidth-1]
						wcsr = IT214_WIDTHCHANGESIZE[width]
						if swidth <= 6 and self.is16:
							wcsl += 1
						if (width+1) <= 6 and self.is16:
							wcsr += 1
						
						
						twidth = width
						if i == self.base_length:
							keep_down = wcsl+(width+1)*length
							raise_left = swidth*length
							
							if keep_down <= raise_left or (width+1) > swidth:
								twidth = width+1
							else:
								twidth = swidth
						else:
							keep_down = wcsl+(width+1)*length+wcsr
							raise_left = swidth*length+wcsl
							raise_right = wcsl+bwt[i]*length
							if bwt[i] == swidth:
								raise_left -= wcsl
								raise_right -= wcsl
							
							if keep_down <= raise_left or (width+1) > swidth:
								if keep_down <= raise_right or (width+1) > bwt[i]:
									twidth = width+1
								else:
									twidth = bwt[i]
							elif raise_left < raise_right or (width+1) > bwt[i]:
								twidth = swidth
							else:
								twidth = bwt[i]
						
						if twidth != width+1:
							for j in xrange(beg,i,1):
								bwt[j] = twidth
						
						if i == self.base_length:
							break
						beg = None
		else: # new "Crater" algorithm
			# determine whether it would be wise to crater stuff
			for width in xrange(self.dwidth-2,0-1,-1):
				print "width", width+1
				beg = None
				swidth = None
				for i in xrange(self.base_length):
					if self.data[i] >= self.lowertab[width] and self.data[i] <= self.uppertab[width]:
						if beg == None:
							swidth = self.dwidth
							if i > 0:
								swidth = bwt[i-1]
							beg = i
						
						if i != self.base_length-1:
							continue
						
						i += 1
					
					if beg != None:
						length = i - beg
						# only if we save bytes do we lower the bit width
						# note, this is a greedy algorithm and might not be optimal
						# UPDATE: it actually isn't.
						
						wcsl = IT214_WIDTHCHANGESIZE[swidth-1]
						wcsr = IT214_WIDTHCHANGESIZE[width]
						if swidth <= 6 and self.is16:
							wcsl += 1
						if (width+1) <= 6 and self.is16:
							wcsr += 1
						
						twidth = swidth
						if i == self.base_length:
							keep_down = wcsl+(width+1)*length
							level_left = swidth*length
							
							if keep_down <= level_left:
								for j in xrange(beg,i,1):
									bwt[j] = width+1
						else:
							keep_down = wcsl+(width+1)*length+wcsr
							level_left = swidth*length+wcsl
							level_right = wcsl+bwt[i]*length
							if bwt[i] == swidth:
								level_left -= wcsl
								level_right -= wcsl
							
							if keep_down <= level_left:
								if keep_down <= level_right:
									for j in xrange(beg,i,1):
										bwt[j] = width+1
						
						
						
						if i == self.base_length:
							break
						beg = None
			
		#print bwt
		
		self.squish_write(bwt)
	
	def squish_write(self, bwt):
		# write values
		print "writing"
		dwidth = self.dwidth
		for i in xrange(self.base_length):
			if bwt[i] != dwidth:
				if dwidth <= 6: # MODE A
					self.write(dwidth, (1<<(dwidth-1)))
					self.write(self.fetch_a, self.convert_width(dwidth,bwt[i]))
				elif dwidth < self.dwidth: # MODE B
					xv = (1<<(dwidth-1))+self.lower_b+self.convert_width(dwidth,bwt[i])
					self.write(dwidth, xv)
				else: # MODE C
					assert (bwt[i]-1) >= 0
					self.write(dwidth, (1<<(dwidth-1))+bwt[i]-1)
				
				dwidth = bwt[i]
			
			assert self.data[i] >= self.lowertab[dwidth-1] and self.data[i] <= self.uppertab[dwidth-1]
			
			if dwidth == self.dwidth:
				assert (self.clamp_unsigned(self.data[i]) & (1<<(self.dwidth-1))) == 0
			self.write(dwidth, self.clamp_unsigned(self.data[i]))
	
	def convert_width(self, curwidth, newwidth):
		curwidth -= 1
		newwidth -= 1
		assert newwidth != curwidth
		if newwidth > curwidth:
			newwidth -= 1
		
		return newwidth

class IT214Decompressor:
	def __init__(self, data, length, is16):
		self.data = data
		self.dpos = 0
		self.bpos = 0
		self.brem = 8
		
		self.base_length = length
		self.grab_length = length
		self.running_count = 0
		
		self.is16 = is16
		self.fetch_a = 4 if is16 else 3
		self.spread_b = 16 if is16 else 8
		self.lower_b = -8 if is16 else -4
		self.upper_b = 7 if is16 else 3
		self.width = self.widthtop = 17 if is16 else 9
		self.unpack_mask = 0xFFFF if is16 else 0xFF
		self.maxgrablen = 0x4000 if is16 else 0x8000
		
		self.unpacked_data = []
		
		try:
			self.unpack()
		except IT214ContinueException, e:
			print "WARNING: IT214ContinueException occurred:", e
			print "This might actually be a bug."
			return # it's OK dear
		except IT214Exception, e:
			print "WARNING! WARNING! SAMPLE DATA DECOMPRESSED BADLY!"
			print "IT214Exception:", e
			print "old running count:", self.running_count
			while self.running_count < self.base_length:
				self.unpacked_data.append(self.unpacked_root)
				self.running_count += 1
			self.running_count = self.base_length
			return
			
	
	def unpack(self):
		#while self.grab_length > 0:
		# I think THIS is what itsex.c meant. --GM
		self.length = min(self.grab_length,self.maxgrablen)
		self.grab_length -= self.length
		print "subchunk length: %i" % self.length
		self.unpacked_root = 0
		while self.length > 0 and not self.end_of_block():
			if self.width == 0 or self.width > self.widthtop:
				raise IT214Exception("invalid bit width")
			
			v = self.read(self.width)
			topbit = (1<<(self.width-1))
			#print self.width,v
			if self.width <= 6: # MODE A
				if v == topbit:
					self.change_width(self.read(self.fetch_a))
					#print self.width
				else:
					self.write(self.width, v, topbit)
			elif self.width < self.widthtop: # MODE B
				if v >= topbit+self.lower_b and v <= topbit+self.upper_b:
					qv = v - (topbit+self.lower_b)
					#print "MODE B CHANGE",self.width,v,qv
					self.change_width(qv)
					#print self.width
				else:
					self.write(self.width, v, topbit)
			else: # MODE C
				if v & topbit:
					self.width = (v & ~topbit)+1
					#print self.width
				else:
					self.write(self.width-1, (v & ~topbit), 0)
		
		print "bytes remaining in block: %i" % (len(self.data)-self.dpos)
	
	def write(self, width, value, topbit):
		self.running_count += 1
		self.length -= 1
		
		if DECOMPRESS_IT214:
			v = value
			if v&topbit:#(1<<(width-1)):
				v -= topbit*2#1<<width
			self.unpacked_root = (self.unpacked_root+v) & self.unpack_mask
			self.unpacked_data.append(self.unpacked_root)
	
	def change_width(self, width):
		width += 1
		if width >= self.width:
			width += 1
		
		assert self.width != width # EDOOFUS
		self.width = width
	
	def get_length(self):
		return self.running_count
	
	def get_data(self):
		return self.unpacked_data
	
	def end_of_block(self):
		return self.dpos >= len(self.data)
	
	def read(self, width):
		v = 0
		vpos = 0
		vmask = (1<<width)-1
		while width >= self.brem:
			if self.dpos >= len(self.data):
				raise IT214Exception("unbalanced block end")
			
			v |= (ord(self.data[self.dpos])>>self.bpos)<<vpos
			vpos += self.brem
			width -= self.brem
			self.dpos += 1
			self.brem = 8
			self.bpos = 0
		
		if width > 0:
			if self.dpos >= len(self.data):
				raise IT214Exception("unbalanced block end")
			
			v |= (ord(self.data[self.dpos])>>self.bpos)<<vpos
			v &= vmask
			self.brem -= width
			self.bpos += width
		
		return v

class ITSampleData(ITFloater):
	def __init__(self, sample, fp, length, cvt, flags):
		if flags & 2:
			print "WARNING: Sample is 16-bit. Consider converting to 8-bit."
		if flags & 4:
			print "WARNING: Sample is stereo. Consider converting to mono."
			print "Stereo samples don't play in stereo in IT, by the way."
			print "Plus, S3M-style stereo (left then right) screws up in MadTracker 2."
			if flags & 8:
				print "...compressed stereo? WHAT THE HELL!!!?"
			
			if STEREO_TAKELEFT:
				print "THIS SAMPLE WILL BE REDUCED TO MONO."
				flags &= ~4
				sample.flags &= ~4
		
		if flags & 4: # easy enough to deal with
			length *= 2
		
		if flags & 8:
			print "Decompressing sample data to work out length..."
			print "Sample bit depth: %i-bit" % (16 if (flags & 2) else 8)
			rootptr = fp.tell()
			
			if DECOMPRESS_IT214:
				self.data = []
			xlen = length
			do_stereo = (flags & 4) != 0
			if do_stereo:
				xlen >>= 1
			while xlen > 0:
				blkcomplen, = struct.unpack("<H",fp.read(2))
				# NOTE: I may have misunderstood itsex.c. --GM
				#if blkcomplen >= 0x8000:
				#	print "WARNING: Compressed block length is > 32KB."
				#	print "You most likely didn't use ImpulseTracker."
				
				print "compressed: %i" % blkcomplen
				
				decomp = IT214Decompressor(fp.read(blkcomplen), xlen, (flags & 2) != 0)
				if DECOMPRESS_IT214:
					xdata = decomp.get_data()
					if cvt & 4:
						print "undeltafying IT215 sample"
						base = 0
						if flags & 2:
							for i in xrange(len(xdata)):
								base += xdata[i]
								base &= 0xFFFF
								xdata[i] = base
						else:
							for i in xrange(len(xdata)):
								base += xdata[i]
								base &= 0xFF
								xdata[i] = base
					
					self.data += xdata
				
				blkdecomplen = decomp.get_length()
				print "decompressed: %i" % blkdecomplen
				print "ratio: %.2f" % (float(blkcomplen*(50 if (flags & 2) else 100))/blkdecomplen)
				xlen -= blkdecomplen
				print "remain: %i" % xlen
				if xlen <= 0 and do_stereo:
					print "Decompressing second channel"
					xlen = length>>1
					do_stereo = False
				print
			
			endptr = fp.tell()
			
			if DECOMPRESS_IT214:
				if flags & 2:
					l = self.data
					self.data = []
					for v in l:
						self.data.append(v&0xFF)
						self.data.append(v>>8)
				
				self.data = ''.join(chr(v) for v in self.data)
				
				sample.flags &= ~8
				sample.cvt &= ~4
				cvt &= ~4
			else:
				fp.seek(rootptr)
				self.data = fp.read(endptr-rootptr)
			
		else:
			self.data = fp.read(length*2 if (flags & 2) else length)
		
		
		if cvt & ~5:
			raise Exception("most conversions not supported yet")
		
		if cvt & 4:
			# de-delta the data
			print "Doing delta --> regular conversion."
			print "WARNING: UNTESTED."
			l = []
			base = 0
			if flags & 2:
				for i in xrange(length):
					v = ord(self.data[i*2])|(ord(self.data[i*2+1])<<8)
					base += v
					base &= 0xFFFF
					l.append(base&0xFF)
					l.append(base>>8)
			else:
				for i in xrange(length):
					v = ord(self.data[i])
					base += v
					base &= 0xFF
					l.append(base)
			
			sample.cvt &= ~4
			self.data = ''.join(chr(v) for v in l)
		
		if not (cvt & 1):
			# sign the data
			print "Doing unsigned --> signed conversion."
			print "WARNING: UNTESTED."
			
			l = []
			if flags & 2:
				for i in xrange(length):
					l.append(ord(self.data[i*2]))
					l.append(ord(self.data[i*2+1])^0x80)
			else:
				for i in xrange(length):
					l.append(ord(self.data[i])^0x80)
			
			sample.cvt &= ~1
			self.data = ''.join(chr(v) for v in l)
		
		# they can get it in their current form
		# also, IT214 + cvt 0x04 (delta) = IT215
		#if not (cvt & 1):
		#	raise Exception("unsigned-to-signed conversion not supported yet")
		
		if COMPRESS_IT214 and not (sample.flags & 8):
			print "Compressing sample data FOR THE SMULZ"
			print "Sample bit depth: %i-bit" % (16 if (flags & 2) else 8)
			offs = 0
			xlen = length
			unpacked_data = self.data
			self.data = []
			print "uncompressed: %i" % length
			totblkcomplen = 0
			do_stereo = (flags & 4) != 0
			if do_stereo:
				xlen >>= 1
			while xlen > 0:
				comp = IT214Compressor(unpacked_data, offs, xlen, (flags&2) != 0, False)
				self.data += comp.get_data()
				blkuncomplen = comp.get_length()
				offs += blkuncomplen
				xlen -= blkuncomplen
				if xlen <= 0 and do_stereo: # doing it XMPlay-style
					xlen = length>>1
					do_stereo = False
			blkcomplen = len(self.data)
			print "compressed: %i" % blkcomplen
			print "ratio: %.2f" % (float(blkcomplen*100)/length)
			
			using_it215 = False
			if COMPRESS_IT215:
				print "Recompressing sample data as IT215"
				offs = 0
				xlen = length
				it215data = []
				print "uncompressed: %i" % length
				totblkcomplen = 0
				do_stereo = (flags & 4) != 0
				if do_stereo:
					xlen >>= 1
				while xlen > 0:
					comp = IT214Compressor(unpacked_data, offs, xlen, (flags&2) != 0, True)
					it215data += comp.get_data()
					blkuncomplen = comp.get_length()
					offs += blkuncomplen
					xlen -= blkuncomplen
					if xlen <= 0 and do_stereo: # doing it XMPlay-style
						xlen = length>>1
						do_stereo = False
				blkcomplen215 = len(it215data)
				print "compressed (214): %i" % blkcomplen
				print "compressed (215): %i" % blkcomplen215
				print "ratio (215): %.2f" % (float(blkcomplen215*100)/length)
				if blkcomplen215 < blkcomplen:
					print "using IT215 sample, YES"
					self.data = it215data
					using_it215 = True
				else:
					print "using IT214 sample"
			
			if len(self.data) < len(unpacked_data):
				print "compression successful"
				self.data = ''.join(chr(v) for v in self.data)
				sample.flags |= 8
				if using_it215:
					sample.cvt |= 4
			else:
				print "COMPRESSION SUCKED, USING NORMAL SAMPLE DATA"
				self.data = unpacked_data
		
		self.pack()
	
	def use(self, module):
		self.currently_used = True
	
	def pack(self):
		self.mask = [ord(v) for v in self.data]

class ITInstrument(ITFloater):
	def __init__(self, fp):
		imps = fp.read(4)
		if imps != "IMPI":
			print "WARNING: Instrument w/o IMPI header"
		self.filename = fp.read(13)
		if self.filename[-1] != "\x00":
			print "WARNING: Instrument filename w/o null terminator"
		self.nna, self.dct, self.dca, self.fadeout = struct.unpack("<BBBH", fp.read(5))
		self.pps, self.ppc, self.gvol, self.dfp, self.rv, self.rp = struct.unpack("<BBBBBB", fp.read(6))
		fp.read(4) # skip IT instrument file specifics
		self.name = fp.read(26)
		if self.name[-1] != "\x00":
			print "WARNING: Instrument name w/o null terminator"
		self.ifc, self.ifr, self.mch, self.mpr, self.midibnk = struct.unpack("<BBBBH", fp.read(6))
		self.nstab = [[ord(fp.read(1)),ord(fp.read(1))] for i in xrange(120)]
		self.envs = [
			[ord(v) for v in fp.read(6)] # Flg Num LpB LpE SLB SLE
			+
			[
				[[ord(v) for v in fp.read(3)] for i in xrange(25)]
			] + [fp.read(1)]
			for env in xrange(3)]
		
		self.nsused = [False for i in xrange(120)]
		self.smpused = {}
		self.currently_used = False
	
	def patuse(self, module, note):
		if not self.nsused[note]:
			smp = self.nstab[note][1]-1
			#print note, smp
			module.make_use_of(module.smplist[smp],"sample",smp)
		
		self.nsused[note] = True
	
	def use(self, module):
		if not self.currently_used:
			pass
		
		self.currently_used = True
	
	def remap_smp(self, smpmap):
		for i in xrange(120):
			if self.nsused[i] and self.nstab[i][1] != 0:
				self.nstab[i][1] = smpmap[self.nstab[i][1]-1]+1
	
	def pack(self):
		self.mask = [ord(v) for v in "IMPI"] + [None]*12
		self.mask += [0,self.nna, self.dct, self.dca, self.fadeout&0xFF, self.fadeout>>8]
		self.mask += [self.pps, self.ppc, self.gvol, self.dfp, self.rv, self.rp] + [None]*(4+25)
		self.mask += [0,self.ifc, self.ifr, self.mch, self.mpr, self.midibnk&0xFF, self.midibnk>>8]
		
		# TODO? rearrange notation?
		for i in xrange(120):
			if self.nsused[i]:
				self.mask += self.nstab[i]
			else:
				self.mask += [None]*2
		
		for env in self.envs:
			if env[0] & 1:
				if env[1] >= 25:
					print "WARNING: Envelope length is too large! Clamping to 25."
					env[1] = 25
				
				self.mask += [env[0],env[1]]
				
				if env[0] & 2:
					self.mask += [env[2],env[3]]
				else:
					self.mask += [None]*2
				
				if env[0] & 4:
					self.mask += [env[4],env[5]]
				else:
					self.mask += [None]*2
				
				for i in xrange(25):
					if i < env[1]:
						self.mask += env[6][i]
					else:
						self.mask += [None]*3
			else:
				#self.mask += [0] + [None]*(25*3+5)
				# this can save schism & other things some serious grief
				self.mask += [0,2,None,None,None,None,64,0,0,64,100,0] + [None]*(23*3)
			
			self.mask += [None]

class ITSample(ITFloater):
	def __init__(self, fp):
		imps = fp.read(4)
		if imps != "IMPS":
			print "WARNING: Sample w/o IMPS header"
		self.filename = fp.read(13)
		if self.filename[-1] != "\x00":
			print "WARNING: Sample filename w/o null terminator"
		self.gvl, self.flags, self.vol = struct.unpack("<BBB", fp.read(3))
		self.name = fp.read(26)
		if self.name[-1] != "\x00":
			print "WARNING: Sample name w/o null terminator"
		
		(
			self.cvt, self.dfp, 
			self.length, self.lpbeg, self.lpend, self.freq,
			self.susbeg, self.susend, smpptr,
			self.vis, self.vid, self.vir, self.vit
		) = struct.unpack("<BBIIIIIIIBBBB", fp.read(34))
		
		if self.flags & 0x10:
			if self.lpbeg > self.lpend:
				print "WARNING: Loop start is greater than loop end"
			if self.lpend > self.length:
				print "WARNING: Loop end is greater than length"
		if self.flags & 0x20:
			if self.susbeg > self.susend:
				print "WARNING: Susloop start is greater than susloop end"
			if self.susend > self.length:
				print "WARNING: Susloop end is greater than length"
		
		if self.length == 0:
			if (self.flags & 1):
				print "WARNING: Sample data is supposed to exist but length is 0."
				self.flags &= ~1
		
		if (self.flags & 1):
			fp.seek(smpptr)
			if smpptr == 0:
				print "WARNING: Many trackers/players don't load sampledata with a pointer of 0."
			self.smpdata = ITSampleData(self, fp, self.length, self.cvt, self.flags)
		elif smpptr != 0:
			print "WARNING: Sample pointer is nonzero but bit 0 of flags is clear."
			print "Either your tracker is broken, or you've packed this already."
			self.smpdata = None
		
		self.currently_used = False
	
	def use(self, module):
		if not self.currently_used:
			if self.smpdata:
				module.make_use_of(self.smpdata,"sampledata",0)
				self.pack()
			else:
				return # don't mark an empty sample as used!
		
		
		self.currently_used = True
	
	def pack(self):
		self.mask = [ord(v) for v in "IMPS"] + [None]*12
		self.mask += [0,self.gvl,self.flags,self.vol] + [None]*25
		self.mask += [0,self.cvt,self.dfp]
		self.mask += [ord(v) for v in struct.pack("<I",self.length)]
		if self.flags & 0x10:
			self.mask += [ord(v) for v in struct.pack("<II",self.lpbeg,self.lpend)]
		else:
			self.mask += [None]*8
		
		self.mask += [ord(v) for v in struct.pack("<I",self.freq)]
		
		if self.flags & 0x20:
			self.mask += [ord(v) for v in struct.pack("<II",self.susbeg,self.susend)]
		else:
			self.mask += [None]*8
		
		self.mask += [-1 if (self.flags & 1) else None]*4
		
		# TODO make suitable gap for vibrato type
		self.mask += [self.vis,self.vid,self.vir,self.vit]
	
	def saveptr(self, modmask):
		if self.smpdata:
			koffs = self.file_crap_offs+0x48
			for v in struct.pack("<I",self.smpdata.file_crap_offs):
				modmask[koffs] = ord(v)
				koffs += 1

class ITModule(ITFloater):
	dynamic = False
	def __init__(self, fname):
		self.currently_used = False
		
		fp = open(fname,"rb")
		
		impm = fp.read(4)
		if impm != "IMPM":
			raise Exception("IMPM magic missing - sure this is an .it file?")
		
		self.name = fp.read(26)
		if self.name[-1] != "\x00":
			print "WARNING: Song name w/o null terminator"
		
		self.hilite, ordnum, insnum, smpnum, patnum = struct.unpack("<HHHHH", fp.read(10))
		self.cwt, self.cmwt, self.flags, self.special = struct.unpack("<HHHH", fp.read(8))
		self.gvol, self.mvol, self.ispd, self.itpo, self.sep, self.pwd = struct.unpack("<BBBBBB", fp.read(6))
		msglen, msgoffs, timestamp = struct.unpack("<HII", fp.read(10))
		self.cpan = [ord(v) for v in fp.read(64)]
		self.cvol = [ord(v) for v in fp.read(64)]
		self.ordlist = [ord(v) for v in fp.read(ordnum)]
		if self.ordlist[-1] != 0xFF:
			print "WARNING: Last order is not an end-of-song marker"
		if 0xFE in self.ordlist:
			print "WARNING: Song separators (0xFE) found in orderlist."
			print "It is recommended that you take these out."
		if self.special & 1:
			print "NOTE: Song contained message. This will be nuked."
			self.special &= ~1
		if (self.flags & 128) or (self.special & 8):
			print "NOTE: Song contained MIDI data. This will be nuked (plus I don't know how to load it)."
			self.flags &= ~128
			self.special &= ~8
		
		insptrlist = [struct.unpack("<I", fp.read(4))[0] for i in xrange(insnum)]
		smpptrlist = [struct.unpack("<I", fp.read(4))[0] for i in xrange(smpnum)]
		patptrlist = [struct.unpack("<I", fp.read(4))[0] for i in xrange(patnum)]
		
		self.inslist = []
		for ptr in insptrlist:
			fp.seek(ptr)
			if self.cmwt < 0x0200:
				# TODO? attempt IT 1.xx instruments?
				raise Exception("old IT instruments not supported")
			self.inslist.append(ITInstrument(fp))
		
		self.smplist = []
		for ptr in smpptrlist:
			fp.seek(ptr)
			self.smplist.append(ITSample(fp))
		
		self.patlist = []
		for ptr in patptrlist:
			if ptr == 0:
				self.patlist.append(None)
			else:
				fp.seek(ptr)
				self.patlist.append(ITPattern(fp))
		
		fp.close()
		
		self.chn_has_sound = [False for i in xrange(64)]
		
		self.usageset = set()
		
		self.finalinslist = []
		self.finalsmplist = []
		self.finalpatlist = []
		self.finalsmpdatalist = []
		
		self.insmap = {}
		self.smpmap = {}
		self.patmap = {}
		
		# Indicate what's stored.
		self.make_use_of(self,"module",0)
		
		# Remove self from usageset
		self.usageset.remove(self)
		
		insnum = len(self.finalinslist)
		smpnum = len(self.finalsmplist)
		patnum = len(self.finalpatlist)
		
		# remap order list
		for i in xrange(len(self.ordlist)):
			v = self.ordlist[i]
			if v < len(self.patlist):
				self.ordlist[i] = self.patmap[v]
		
		# remap instruments
		for ins in self.finalinslist:
			ins.remap_smp(self.smpmap)
			ins.pack()
		
		# remap patterns
		smpinsmap = self.insmap if (self.flags & 4) else self.smpmap
		for pat in self.finalpatlist:
			pat.remap_smpins(smpinsmap)
			pat.optimise(self)
			pat.pack()
		
		print "Orders: %i" % (ordnum)
		print "Instruments: %i -> %i" % (len(self.inslist),insnum)
		print "Samples: %i -> %i" % (len(self.smplist),smpnum)
		print "Patterns: %i -> %i" % (len(self.patlist),patnum)
		
		self.cwt = 0x7FFF
		self.cmwt = 0x0215
		self.mask = [ord(v) for v in "IMPM"+self.name]
		self.mask += [ord(v) for v in struct.pack("<HHHHH", self.hilite, ordnum, insnum, smpnum, patnum)]
		self.mask += [ord(v) for v in struct.pack("<HHHH", self.cwt, self.cmwt, self.flags, self.special)]
		self.mask += [self.gvol, self.mvol, self.ispd, self.itpo, self.sep, None]
		self.mask += [None]*(2+4+4)
		self.mask += [self.cpan[i] if self.chn_has_sound[i] else None for i in xrange(64)]
		self.mask += [self.cvol[i] if self.chn_has_sound[i] else None for i in xrange(64)]
		self.mask += self.ordlist
		self.mask += [-1,-1,-1,-1]*(insnum+smpnum+patnum)
		self.mask += [0,0]
	
	def make_use_of(self, thing, typ, index):
		thing.use(self)
		
		if not thing.currently_used:
			return
		
		if thing not in self.usageset:
			if typ == "pattern":
				self.patmap[index] = len(self.finalpatlist)
				self.finalpatlist.append(thing)
			elif typ == "sample":
				self.smpmap[index] = len(self.finalsmplist)
				self.finalsmplist.append(thing)
			elif typ == "instrument":
				self.insmap[index] = len(self.finalinslist)
				self.finalinslist.append(thing)
			elif typ == "sampledata":
				self.finalsmpdatalist.append(thing)
			elif typ == "module":
				assert thing == self
			else:
				raise Exception("EDOOFUS: \"%s\" is not a valid block type")
			
			self.usageset.add(thing)
		
	
	def use(self, module):
		assert self == module # i.e. don't be stupid
		
		if not self.currently_used:
			q = False
			for patidx in self.ordlist:
				if patidx < len(self.patlist):
					q = True
					module.make_use_of(self.patlist[patidx],"pattern",patidx)
			
			if not q:
				print "ATTEMPTING TO PRODUCE SAMPLEPACK"
				if self.flags & 4:
					for idx in xrange(len(self.inslist)):
						module.make_use_of(self.inslist[idx],"instrument",idx)
				
				for idx in xrange(len(self.smplist)):
					module.make_use_of(self.smplist[idx],"sample",idx)
		
		self.currently_used = True
	
	def save(self, fname):
		fp = open(fname,"wb")
		
		rootoffs = 1
		
		self.calculate_first_instance_map(1, len(self.mask)-1)
		
		for thing in self.usageset:
			# oh boy, the OO-purists are just going to *LOVE* this...
			thing.last_floater = 1
		
		while self.usageset:
			
			# using <del>KMP... there may be a partial match, so we'll not do this skip</del>
			# nope, back to the old thing.
			#while rootoffs < len(self.mask) and self.mask[rootoffs] != None:
			#	rootoffs += 1
			
			bestthing = None
			bestoffs = 1073741824 # do you really have a 1GB .it file?
			for thing in self.usageset:
				offs = self.compare_floaters(thing,thing.last_floater)
				thing.last_floater = offs
				if offs < bestoffs:
					bestthing = thing
					bestoffs = offs
			
			self.usageset.remove(bestthing)
			
			print ("adding %i" % bestoffs), bestthing
			
			bestthing.file_crap_offs = bestoffs
			for i in xrange(len(bestthing.mask)):
				o = i+bestoffs
				if o >= len(self.mask):
					chunk = bestthing.mask[i:]
					self.mask += chunk
					for j in xrange(len(chunk)):
						v = chunk[j]
						if v == None:
							self.none_instance_map.append(o+j)
						elif v != -1:
							heapq.heappush(self.first_instance_map[v], o+j)
					
					break
				if self.mask[o] == None:
					v = bestthing.mask[i]
					if v != None:
						self.none_instance_map.remove(o)
						heapq.heappush(self.first_instance_map[v],o)
						self.mask[o] = bestthing.mask[i]
				elif bestthing.mask[i] != None:
					assert self.mask[o] == bestthing.mask[i]
			
			heapq.heapify(self.none_instance_map)
		
		pmaptab = self.finalinslist + self.finalsmplist + self.finalpatlist
		koffs = 0x00C0 + len(self.ordlist)
		
		for i in xrange(len(pmaptab)):
			thing = pmaptab[i]
			for v in struct.pack("<I",thing.file_crap_offs):
				self.mask[koffs] = ord(v)
				koffs += 1
		
		for smp in self.finalsmplist:
			smp.saveptr(self.mask)
		
		s = "MUNCH*PY|"
		for v in self.mask:
			if v == None:
				fp.write(s[0])
				s = s[1:] + s[0]
			else:
				fp.write(chr(v))
		
		fp.close()

if len(sys.argv) <= 2:
	print "usage:\n\tpython munch.py infile.it outfile.it"
	exit()

module = ITModule(sys.argv[1])
module.save(sys.argv[2])
