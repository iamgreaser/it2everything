import sys, struct

"""
Explanation of the compression scheme:

Header:
magic number 0xC2190001, big-endian
32-bit LE length

Chunk length table:
elias delta values (1 = 1, 010 = 2, 011 = 3)
we stop when we get a 1 in the table
otherwise, the value + 1 stored is the length of this chunk

Main stream:
sign-extended w-bit number, w initialised with 8
initial direction is positive

1 = progress "forward" 1 (if used in bit width 8, output -128 instead)
01 = change direction THEN progress "forward" 1 (same comment wrt bit width 8)
00xxx = change bit width to x+1, direction unchanged

note, if bit width is 1, it behaves differently...
ED value = length
then 3 bits = new bit width (add 1 to this number to get it)

"""

class BitStreamWriter:
	def __init__(self, fp):
		self.fp = fp
		self.reset()
	
	def reset(self):
		self.bval = 0
		self.brem = 8
		self.bpos = 0
	
	def flush(self):
		if self.bpos > 0:
			self.fp.write(chr(self.bval))
			self.reset()
	
	def write(self, w, v):
		if v >= (1<<w):
			raise Exception("v should not exceed w bits")
		if v < 0:
			raise Exception("v should not be negative")
		
		while w > self.brem:
			self.bval |= (v<<self.bpos)&255
			w -= self.brem
			v >>= self.brem
			self.flush()
		
		self.bval |= v<<self.bpos
		self.bpos += w
		self.brem -= w
	
	def write_ed(self, v):
		if v < 1:
			raise Exception("v should be >= 1")
		
		k = 2
		w = 0
		while v >= k:
			self.write(1, 0)
			k <<= 1
			w += 1
		self.write(1, 1)
		self.write(w, v-(k>>1))

bw = [9 for i in xrange(256)]
for i in xrange(8):
	p = 8-i
	q = (1<<(p-1))
	for j in xrange(-(q-1),q,1):
		bw[j+128] = p

#print bw

def log2(v):
	#r = 0
	#s = 1
	#while v >= s:
	#	r += 1
	#	s <<= 1
	#return r
	return bw[v+128]

def log2ed(v):
	r = 1
	s = 2
	while v >= s:
		s <<= 1
		r += 2
	
	return r

def abssum(l):
	r = 0
	for v in l:
		r += log2(v)
		#r += abs(v)
	
	return r

def rs8(v):
	return ((v+128)&255)-128

# load sample
fp = open(sys.argv[1],"rb")
l = [rs8(ord(v)) for v in fp.read()]
fp.close()
print l

# find optimal chain
ls, lc, ll = 0, abssum(l), l
print ls, lc
clc = []
bll = []
ccx = 0

# note, attempting to make a perfect chain is a dumb idea as it takes too long
# limiting it to 520.
for j in xrange(1,min(520+1,len(l)),1):
	cl = ll[:j]
	for v,vp in zip(l[j:],l[:-j]):
		cl.append(rs8(v-vp))
	
	q = abssum(cl)+len(clc)+log2ed((j-ccx)+1)
	if q < lc:
		ccx = j
		ls, lc, ll = j, q, cl
		clc.append(j)
		print ">", ls, lc
	
	#bll.append(cl)
	if j%100 == 0:
		print j, abssum(cl)

# calculate minimum bit widths
print ll
print "Optimal chain:", clc
bwl = [log2(v) for v in ll]
print len(bwl), sum(bwl), (sum(bwl)+7)/8, (sum(bwl)+5*len(bwl)+7)/8

# CRATER ALGORITHM.
# this usually fares better than Impulse Tracker itself when applied to IT214.
# however, said implementation has been proven suboptimal.
# said implementation is the default compressor as used in munch.py :)
#   (mostly because it's a lot nicer and easier to follow than the fillin algorithm)
# TODO: deal with direction flag here
def crater(l,ll,s,e,w):
	lower_start = None
	#print w,s,e
	for i in xrange(s,e+1,1):
		if i < e:
			l[i] = w
		# find stretches
		# note, we can't actually read l[e] here.
		# nor can we reduce w below 1.
		if w > 1 and i < e and ll[i] < w:
			if lower_start == None:
				lower_start = i
		elif lower_start != None:
			# calculate stretch length
			lg = i-lower_start
			
			# calculate direct stretch bit count
			bc = lg*(w-1)
			gbc = lg*w
			
			# calculate left/right change sizes if necessary
			# TODO: simplify to 2 (or 1 if dir flag is implemented)
			# TODO: dig deeper crater if necessary (could fix optimality issue)
			if lower_start != s:
				bc += w+5
			if i != e:
				if w-1 == 1:
					bc = log2ed(lg)+3
				else:
					bc += (w-1)+5
			
			if bc <= gbc:
				crater(l,ll,lower_start,i,w-1)
			
			lower_start = None

# apply crater algorithm to calculate "optimal enough" bit widths
fbwl = [8]*len(bwl)
crater(fbwl,bwl,0,len(bwl),8)
#print fbwl

print (sum(fbwl)+7)/8

# save compressed sample
# save header
fp = open(sys.argv[2],"wb")
fp.write("\xC2\x19\x00\x01")
fp.write(struct.pack("<I",len(ll)))
bfp = BitStreamWriter(fp)

# write CLT
for v,vp in zip(clc,[0]+clc[:-1]):
	bfp.write_ed(1+(v-vp))
bfp.write_ed(1)

# write stream
go = -1
cw = 8
rlez = 0
for w,v in zip(fbwl,ll):
	assert cw >= 1 and cw <= 8, "bit width out of range! bad stream!"
	
	# check if width needs change
	if w != cw:
		# check if width is 1
		if cw == 1:
			# write elias delta length
			bfp.write_ed(rlez)
			rlez = 0
			
			# write width
			bfp.write(3,w-1)
			
			cw = w
		else:
			# write width change value
			bfp.write(cw,(1<<(cw-1)))
			# select width change type
			if w == cw-go:
				bfp.write(1,0)
				bfp.write(1,1)
				go = -go
			elif w == cw+go:
				bfp.write(1,1)
			else:
				bfp.write(2,0)
				bfp.write(3,w-1)
			
			cw = w
	
	# check if -128 (0x80)
	# cw should be 8 by this point
	if v == -128:
		bfp.write(8,0x80)
		if go == -1:
			bfp.write(1,0)
			go = -go
		bfp.write(1,1)
	elif cw == 1:
		rlez += 1
	else:
		# write sample data
		bfp.write(cw,v&((1<<cw)-1))

if rlez >= 1:
	bfp.write_ed(rlez)

print fbwl
print ll

# close file
bfp.flush()
fp.close()

