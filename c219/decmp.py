import sys, struct, time

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

def rs8(v):
	return ((v+128)&255)-128

class BitStreamReader:
	def __init__(self, fp):
		self.fp = fp
		self.bw = 8
		self.dir = -1
		self.rlez = -1
		self.reset()
	
	def reset(self):
		self.bval = 0
		self.brem = 0
	
	def flush(self):
		self.reset()
	
	def fetch(self):
		self.bval = ord(self.fp.read(1))
		self.brem = 8
	
	def read_c219(self):
		while True:
			#print "q",self.bw
			
			if self.rlez > 0:
				self.rlez -= 1
				return 0
			elif self.rlez == 0 and self.bw == 1:
				self.rlez = -1
				self.bw = self.read(3)+1
			
			if self.bw == 1:
				self.rlez = self.read_ed()
				continue
			
			if self.bw == 9:
				self.bw = 8
				return -128
			
			assert self.bw >= 1 and self.bw <= 8, "bit width out of range! bad stream!"
			
			v = self.read(self.bw)
			if v == (1<<(self.bw-1)):
				if self.read(1) == 1: # 1
					#print "inc dir"
					self.bw += self.dir
				elif self.read(1) == 1: # 01
					#print "dec dir"
					self.dir = -self.dir
					self.bw += self.dir
				else: # 00xxx
					#print "set"
					self.bw = self.read(3)+1
			else:
				if (v & (1<<(self.bw-1))) != 0:
					v |= 0xFF<<self.bw
				return rs8(v)
			
	
	def read(self, w):
		r = 0
		rp = 0
		while w > self.brem:
			r |= self.bval << rp
			rp += self.brem
			w -= self.brem
			self.fetch()
		
		r |= (self.bval & ((1<<w)-1)) << rp
		self.bval >>= w
		self.brem -= w
		
		return r
	
	def read_ed(self):
		w = 0
		v = 1
		
		while self.read(1) == 0:
			v <<= 1
			w += 1
		
		v |= self.read(w)
		
		return v

ifp = open(sys.argv[1],"rb")
bfp = BitStreamReader(ifp)

magic = ifp.read(4)
size, = struct.unpack("<I",ifp.read(4))
if magic != "\xC2\x19\x00\x01":
	raise Exception("not a C219 sample")

chains = []
ov = 0
while True:
	v = bfp.read_ed()
	if v == 1:
		break
	v -= 1
	ov = ov+v
	chains.append(ov)

chains.append(size)

print chains

l = []
c = 0
cv = 0
for i in xrange(size):
	if i == chains[c]:
		cv = i
		c += 1
	
	v = bfp.read_c219()
	if cv != 0:
		v = rs8(v+l[-cv])
	
	#print i,v
	l.append(v)
	#time.sleep(0.1)

print l

ofp = open(sys.argv[2],"wb")
for v in l:
	ofp.write(chr(v&255))
ofp.close()
ifp.close()

