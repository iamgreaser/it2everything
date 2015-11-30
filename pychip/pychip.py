#!/usr/bin/env python --
#
# PyChip: an NSF composer system | by Ben "GreaseMonkey" Russell, 2010
# Public domain. Because your music is too meaningful to be copyrighted.

import math
import sys
import struct

CLK_NTSC = 21477272
CLK_PAL  = 26601712

# 6502 opcode table
# converted from: http://www.oxyron.de/html/opcodes02.html
OPTAB = {
	'ADC:zp':{'index': 101, 'clocks': 3, 'clkinc': False},
	'CPY:abs':{'index': 204, 'clocks': 4, 'clkinc': False},
	'ISC:zp':{'index': 231, 'clocks': 5, 'clkinc': False},
	'INY:':{'index': 200, 'clocks': 2, 'clkinc': False},
	'SED:':{'index': 248, 'clocks': 2, 'clkinc': False},
	'BRK:':{'index': 0, 'clocks': 7, 'clkinc': False},
	'AND:izy':{'index': 49, 'clocks': 5, 'clkinc': True},
	'ISC:aby':{'index': 251, 'clocks': 7, 'clkinc': False},
	'CPY:imm':{'index': 192, 'clocks': 2, 'clkinc': False},
	'BVS:rel':{'index': 112, 'clocks': 2, 'clkinc': True},
	'LDY:abx':{'index': 188, 'clocks': 4, 'clkinc': True},
	'SLO:zpx':{'index': 23, 'clocks': 6, 'clkinc': False},
	'TAY:':{'index': 168, 'clocks': 2, 'clkinc': False},
	'DCP:aby':{'index': 219, 'clocks': 7, 'clkinc': False},
	'LAS:aby':{'index': 187, 'clocks': 4, 'clkinc': True},
	'DEY:':{'index': 136, 'clocks': 2, 'clkinc': False},
	'EOR:imm':{'index': 73, 'clocks': 2, 'clkinc': False},
	'ARR:imm':{'index': 107, 'clocks': 2, 'clkinc': False},
	'SRE:zp':{'index': 71, 'clocks': 5, 'clkinc': False},
	'LDX:abs':{'index': 174, 'clocks': 4, 'clkinc': False},
	'BPL:rel':{'index': 16, 'clocks': 2, 'clkinc': True},
	'STA:abx':{'index': 157, 'clocks': 5, 'clkinc': False},
	'STA:aby':{'index': 153, 'clocks': 5, 'clkinc': False},
	'BIT:abs':{'index': 44, 'clocks': 4, 'clkinc': False},
	'LDX:aby':{'index': 190, 'clocks': 4, 'clkinc': True},
	'ADC:abx':{'index': 125, 'clocks': 4, 'clkinc': True},
	'KIL:':{'index': 242, 'clocks': -1, 'clkinc': False},
	'STA:abs':{'index': 141, 'clocks': 4, 'clkinc': False},
	'RRA:zp':{'index': 103, 'clocks': 5, 'clkinc': False},
	'SLO:izy':{'index': 19, 'clocks': 8, 'clkinc': False},
	'ROR:':{'index': 106, 'clocks': 2, 'clkinc': False},
	'CMP:abx':{'index': 221, 'clocks': 4, 'clkinc': True},
	'CMP:aby':{'index': 217, 'clocks': 4, 'clkinc': True},
	'SBC:abx':{'index': 253, 'clocks': 4, 'clkinc': True},
	'SBC:aby':{'index': 249, 'clocks': 4, 'clkinc': True},
	'CMP:abs':{'index': 205, 'clocks': 4, 'clkinc': False},
	'SLO:izx':{'index': 3, 'clocks': 8, 'clkinc': False},
	'SLO:aby':{'index': 27, 'clocks': 7, 'clkinc': False},
	'SHX:aby':{'index': 158, 'clocks': 5, 'clkinc': False},
	'SLO:abs':{'index': 15, 'clocks': 6, 'clkinc': False},
	'ADC:aby':{'index': 121, 'clocks': 4, 'clkinc': True},
	'RLA:zp':{'index': 39, 'clocks': 5, 'clkinc': False},
	'EOR:zp':{'index': 69, 'clocks': 3, 'clkinc': False},
	'ROR:zp':{'index': 102, 'clocks': 5, 'clkinc': False},
	'ROL:zp':{'index': 38, 'clocks': 5, 'clkinc': False},
	'CLV:':{'index': 184, 'clocks': 2, 'clkinc': False},
	'LSR:abs':{'index': 78, 'clocks': 6, 'clkinc': False},
	'DEX:':{'index': 202, 'clocks': 2, 'clkinc': False},
	'TXA:':{'index': 138, 'clocks': 2, 'clkinc': False},
	'LSR:abx':{'index': 94, 'clocks': 7, 'clkinc': False},
	'ROR:zpx':{'index': 118, 'clocks': 6, 'clkinc': False},
	'LDA:abx':{'index': 189, 'clocks': 4, 'clkinc': True},
	'CPY:zp':{'index': 196, 'clocks': 3, 'clkinc': False},
	'ASL:':{'index': 10, 'clocks': 2, 'clkinc': False},
	'LAX:izy':{'index': 179, 'clocks': 5, 'clkinc': True},
	'LAX:izx':{'index': 163, 'clocks': 6, 'clkinc': False},
	'LDY:zp':{'index': 164, 'clocks': 3, 'clkinc': False},
	'SBC:imm':{'index': 235, 'clocks': 2, 'clkinc': False},
	'DEC:zpx':{'index': 214, 'clocks': 6, 'clkinc': False},
	'LDA:zpx':{'index': 181, 'clocks': 4, 'clkinc': False},
	'CPX:zp':{'index': 228, 'clocks': 3, 'clkinc': False},
	'TAS:aby':{'index': 155, 'clocks': 5, 'clkinc': False},
	'ADC:imm':{'index': 105, 'clocks': 2, 'clkinc': False},
	'SBC:zpx':{'index': 245, 'clocks': 4, 'clkinc': False},
	'STX:zp':{'index': 134, 'clocks': 3, 'clkinc': False},
	'CMP:imm':{'index': 201, 'clocks': 2, 'clkinc': False},
	'EOR:izx':{'index': 65, 'clocks': 6, 'clkinc': False},
	'EOR:izy':{'index': 81, 'clocks': 5, 'clkinc': True},
	'JSR:abs':{'index': 32, 'clocks': 6, 'clkinc': False},
	'STA:zp':{'index': 133, 'clocks': 3, 'clkinc': False},
	'SBC:abs':{'index': 237, 'clocks': 4, 'clkinc': False},
	'TAX:':{'index': 170, 'clocks': 2, 'clkinc': False},
	'SRE:abs':{'index': 79, 'clocks': 6, 'clkinc': False},
	'LAX:abs':{'index': 175, 'clocks': 4, 'clkinc': False},
	'RRA:zpx':{'index': 119, 'clocks': 6, 'clkinc': False},
	'LAX:aby':{'index': 191, 'clocks': 4, 'clkinc': True},
	'INC:abs':{'index': 238, 'clocks': 6, 'clkinc': False},
	'SRE:abx':{'index': 95, 'clocks': 7, 'clkinc': False},
	'SRE:aby':{'index': 91, 'clocks': 7, 'clkinc': False},
	'TSX:':{'index': 186, 'clocks': 2, 'clkinc': False},
	'TXS:':{'index': 154, 'clocks': 2, 'clkinc': False},
	'STY:zpx':{'index': 148, 'clocks': 4, 'clkinc': False},
	'CMP:izx':{'index': 193, 'clocks': 6, 'clkinc': False},
	'CMP:izy':{'index': 209, 'clocks': 5, 'clkinc': True},
	'SEI:':{'index': 120, 'clocks': 2, 'clkinc': False},
	'DCP:zpx':{'index': 215, 'clocks': 6, 'clkinc': False},
	'LDA:imm':{'index': 169, 'clocks': 2, 'clkinc': False},
	'SBC:zp':{'index': 229, 'clocks': 3, 'clkinc': False},
	'LDA:aby':{'index': 185, 'clocks': 4, 'clkinc': True},
	'DCP:izy':{'index': 211, 'clocks': 8, 'clkinc': False},
	'DCP:izx':{'index': 195, 'clocks': 8, 'clkinc': False},
	'AND:zpx':{'index': 53, 'clocks': 4, 'clkinc': False},
	'SRE:zpx':{'index': 87, 'clocks': 6, 'clkinc': False},
	'CLC:':{'index': 24, 'clocks': 2, 'clkinc': False},
	'RRA:izy':{'index': 115, 'clocks': 8, 'clkinc': False},
	'RRA:izx':{'index': 99, 'clocks': 8, 'clkinc': False},
	'ROL:zpx':{'index': 54, 'clocks': 6, 'clkinc': False},
	'AND:izx':{'index': 33, 'clocks': 6, 'clkinc': False},
	'STA:izx':{'index': 129, 'clocks': 6, 'clkinc': False},
	'SLO:abx':{'index': 31, 'clocks': 7, 'clkinc': False},
	'CMP:zp':{'index': 197, 'clocks': 3, 'clkinc': False},
	'SRE:izx':{'index': 67, 'clocks': 8, 'clkinc': False},
	'SRE:izy':{'index': 83, 'clocks': 8, 'clkinc': False},
	'TYA:':{'index': 152, 'clocks': 2, 'clkinc': False},
	'LDY:zpx':{'index': 180, 'clocks': 4, 'clkinc': False},
	'JMP:abs':{'index': 76, 'clocks': 3, 'clkinc': False},
	'RRA:abs':{'index': 111, 'clocks': 6, 'clkinc': False},
	'LDX:imm':{'index': 162, 'clocks': 2, 'clkinc': False},
	'ASL:zpx':{'index': 22, 'clocks': 6, 'clkinc': False},
	'LDY:imm':{'index': 160, 'clocks': 2, 'clkinc': False},
	'SAX:zpy':{'index': 151, 'clocks': 4, 'clkinc': False},
	'PLP:':{'index': 40, 'clocks': 4, 'clkinc': False},
	'NOP:':{'index': 234, 'clocks': 2, 'clkinc': False},
	'SLO:zp':{'index': 7, 'clocks': 5, 'clkinc': False},
	'INC:abx':{'index': 254, 'clocks': 7, 'clkinc': False},
	'ALR:imm':{'index': 75, 'clocks': 2, 'clkinc': False},
	'ORA:imm':{'index': 9, 'clocks': 2, 'clkinc': False},
	'ROL:abs':{'index': 46, 'clocks': 6, 'clkinc': False},
	'ISC:abx':{'index': 255, 'clocks': 7, 'clkinc': False},
	'ROL:abx':{'index': 62, 'clocks': 7, 'clkinc': False},
	'BEQ:rel':{'index': 240, 'clocks': 2, 'clkinc': True},
	'RRA:aby':{'index': 123, 'clocks': 7, 'clkinc': False},
	'ORA:abx':{'index': 29, 'clocks': 4, 'clkinc': True},
	'ORA:aby':{'index': 25, 'clocks': 4, 'clkinc': True},
	'RRA:abx':{'index': 127, 'clocks': 7, 'clkinc': False},
	'XAA:imm':{'index': 139, 'clocks': 2, 'clkinc': False},
	'ORA:abs':{'index': 13, 'clocks': 4, 'clkinc': False},
	'INC:zpx':{'index': 246, 'clocks': 6, 'clkinc': False},
	'AND:aby':{'index': 57, 'clocks': 4, 'clkinc': True},
	'AND:abx':{'index': 61, 'clocks': 4, 'clkinc': True},
	'SAX:izx':{'index': 131, 'clocks': 6, 'clkinc': False},
	'LSR:zp':{'index': 70, 'clocks': 5, 'clkinc': False},
	'PHA:':{'index': 72, 'clocks': 3, 'clkinc': False},
	'ORA:zp':{'index': 5, 'clocks': 3, 'clkinc': False},
	'ROR:abs':{'index': 110, 'clocks': 6, 'clkinc': False},
	'SAX:abs':{'index': 143, 'clocks': 4, 'clkinc': False},
	'AND:abs':{'index': 45, 'clocks': 4, 'clkinc': False},
	'PHP:':{'index': 8, 'clocks': 3, 'clkinc': False},
	'SEC:':{'index': 56, 'clocks': 2, 'clkinc': False},
	'STA:izy':{'index': 145, 'clocks': 6, 'clkinc': False},
	'LDA:abs':{'index': 173, 'clocks': 4, 'clkinc': False},
	'RTS:':{'index': 96, 'clocks': 6, 'clkinc': False},
	'DCP:abs':{'index': 207, 'clocks': 6, 'clkinc': False},
	'LDA:zp':{'index': 165, 'clocks': 3, 'clkinc': False},
	'ISC:zpx':{'index': 247, 'clocks': 6, 'clkinc': False},
	'LDA:izy':{'index': 177, 'clocks': 5, 'clkinc': True},
	'LDA:izx':{'index': 161, 'clocks': 6, 'clkinc': False},
	'CLI:':{'index': 88, 'clocks': 2, 'clkinc': False},
	'BIT:zp':{'index': 36, 'clocks': 3, 'clkinc': False},
	'STX:abs':{'index': 142, 'clocks': 4, 'clkinc': False},
	'DCP:abx':{'index': 223, 'clocks': 7, 'clkinc': False},
	'LSR:zpx':{'index': 86, 'clocks': 6, 'clkinc': False},
	'EOR:abs':{'index': 77, 'clocks': 4, 'clkinc': False},
	'LDX:zp':{'index': 166, 'clocks': 3, 'clkinc': False},
	'ASL:abx':{'index': 30, 'clocks': 7, 'clkinc': False},
	'BVC:rel':{'index': 80, 'clocks': 2, 'clkinc': True},
	'EOR:abx':{'index': 93, 'clocks': 4, 'clkinc': True},
	'EOR:aby':{'index': 89, 'clocks': 4, 'clkinc': True},
	'SAX:zp':{'index': 135, 'clocks': 3, 'clkinc': False},
	'BCC:rel':{'index': 144, 'clocks': 2, 'clkinc': True},
	'ASL:abs':{'index': 14, 'clocks': 6, 'clkinc': False},
	'AND:zp':{'index': 37, 'clocks': 3, 'clkinc': False},
	'AHX:aby':{'index': 159, 'clocks': 5, 'clkinc': False},
	'LAX:zp':{'index': 167, 'clocks': 3, 'clkinc': False},
	'BNE:rel':{'index': 208, 'clocks': 2, 'clkinc': True},
	'ASL:zp':{'index': 6, 'clocks': 5, 'clkinc': False},
	'SBC:izx':{'index': 225, 'clocks': 6, 'clkinc': False},
	'SBC:izy':{'index': 241, 'clocks': 5, 'clkinc': True},
	'ROL:':{'index': 42, 'clocks': 2, 'clkinc': False},
	'LDX:zpy':{'index': 182, 'clocks': 4, 'clkinc': False},
	'ROR:abx':{'index': 126, 'clocks': 7, 'clkinc': False},
	'ANC:imm':{'index': 43, 'clocks': 2, 'clkinc': False},
	'AXS:imm':{'index': 203, 'clocks': 2, 'clkinc': False},
	'PLA:':{'index': 104, 'clocks': 4, 'clkinc': False},
	'ORA:izx':{'index': 1, 'clocks': 6, 'clkinc': False},
	'ORA:izy':{'index': 17, 'clocks': 5, 'clkinc': True},
	'DEC:abx':{'index': 222, 'clocks': 7, 'clkinc': False},
	'ISC:abs':{'index': 239, 'clocks': 6, 'clkinc': False},
	'CMP:zpx':{'index': 213, 'clocks': 4, 'clkinc': False},
	'LDY:abs':{'index': 172, 'clocks': 4, 'clkinc': False},
	'LAX:zpy':{'index': 183, 'clocks': 4, 'clkinc': False},
	'RLA:aby':{'index': 59, 'clocks': 7, 'clkinc': False},
	'RLA:abx':{'index': 63, 'clocks': 7, 'clkinc': False},
	'STY:zp':{'index': 132, 'clocks': 3, 'clkinc': False},
	'LAX:imm':{'index': 171, 'clocks': 2, 'clkinc': False},
	'CLD:':{'index': 216, 'clocks': 2, 'clkinc': False},
	'RLA:abs':{'index': 47, 'clocks': 6, 'clkinc': False},
	'ORA:zpx':{'index': 21, 'clocks': 4, 'clkinc': False},
	'BMI:rel':{'index': 48, 'clocks': 2, 'clkinc': True},
	'EOR:zpx':{'index': 85, 'clocks': 4, 'clkinc': False},
	'INX:':{'index': 232, 'clocks': 2, 'clkinc': False},
	'INC:zp':{'index': 230, 'clocks': 5, 'clkinc': False},
	'DCP:zp':{'index': 199, 'clocks': 5, 'clkinc': False},
	'BCS:rel':{'index': 176, 'clocks': 2, 'clkinc': True},
	'CPX:imm':{'index': 224, 'clocks': 2, 'clkinc': False},
	'RLA:zpx':{'index': 55, 'clocks': 6, 'clkinc': False},
	'JMP:ind':{'index': 108, 'clocks': 5, 'clkinc': False},
	'ADC:izx':{'index': 97, 'clocks': 6, 'clkinc': False},
	'ADC:izy':{'index': 113, 'clocks': 5, 'clkinc': True},
	'STY:abs':{'index': 140, 'clocks': 4, 'clkinc': False},
	'LSR:':{'index': 74, 'clocks': 2, 'clkinc': False},
	'STA:zpx':{'index': 149, 'clocks': 4, 'clkinc': False},
	'ADC:abs':{'index': 109, 'clocks': 4, 'clkinc': False},
	'AHX:izy':{'index': 147, 'clocks': 6, 'clkinc': False},
	'RLA:izy':{'index': 51, 'clocks': 8, 'clkinc': False},
	'RLA:izx':{'index': 35, 'clocks': 8, 'clkinc': False},
	'STX:zpy':{'index': 150, 'clocks': 4, 'clkinc': False},
	'ADC:zpx':{'index': 117, 'clocks': 4, 'clkinc': False},
	'SHY:abx':{'index': 156, 'clocks': 5, 'clkinc': False},
	'DEC:abs':{'index': 206, 'clocks': 6, 'clkinc': False},
	'DEC:zp':{'index': 198, 'clocks': 5, 'clkinc': False},
	'RTI:':{'index': 64, 'clocks': 6, 'clkinc': False},
	'ISC:izy':{'index': 243, 'clocks': 8, 'clkinc': False},
	'ISC:izx':{'index': 227, 'clocks': 8, 'clkinc': False},
	'CPX:abs':{'index': 236, 'clocks': 4, 'clkinc': False},
	'AND:imm':{'index': 41, 'clocks': 2, 'clkinc': False},
}

class Asm6502:
	# real PC, mapped PC, map limit
	def __init__(self, rpc=0x0000, mpc=0x8000, mlim=0x8000):
		self.rpc = rpc
		self.mpc = mpc
		self.mlim = mlim
		self.mem = []
		self.labels = {}
		self.labrefs = []
	
	def store_labels(self):
		for n,t,rpc,mpc in self.labrefs:
			if n.startswith("<") or n.startswith(">"):
				r = self.labels[n[1:]]
				if t in ["rel","abs","abx","aby","ind"]:
					raise Exception("cannot do small label for "+t)
				
				if n[0] == ">":
					r >>= 8
				
				self.mem[rpc] = r & 0xFF
			else:
				r = self.labels[n]
				if t == "rel":
					r -= mpc+1
					if ((r+0x80) & 0xFF) != (r+0x80):
						raise Exception("branch out of range: %04X -> %04X" % (mpc,self.labels[n]))
				
				self.mem[rpc] = r & 0xFF
				if t != "rel":
					self.mem[rpc+1] = (r >> 8) & 0xFF
	
	def add_label(self,label,mpc):
		label = label.upper()
		if label in self.labels:
			raise Exception("duplicate label: "+label)
		self.labels[label] = mpc
	
	def binary(self, data, align=1, label=None, rpc=None, mpc=None, mlim=None):
		if not mpc:
			mpc = self.mpc
		if not rpc:
			rpc = self.rpc
		if not mlim:
			mlim = self.mlim
		
		if align:
			if int(mpc+len(data)) / int(align) != int(mpc) / int(align):
				while mpc % align:
					mpc += 1
					rpc += 1
					mlim -= 1
					if mlim < 0:
						raise Exception("exceeded mlim")
		
		if label:
			self.add_label(label,mpc)
		
		if type(data) == type(""):
			for c in data:
				self.mem[rpc] = ord(c)
				mpc += 1
				rpc += 1
				mlim -= 1
				if mlim < 0:
					raise Exception("exceeded mlim")
		else:
			for v in data:
				self.mem[rpc] = v
				mpc += 1
				rpc += 1
				mlim -= 1
				if mlim < 0:
					raise Exception("exceeded mlim")
		
		self.rpc = rpc
		self.mpc = mpc
		self.mlim = mlim
	
	def align(self, align):
		while self.mpc % align:
			self.mpc += 1
			self.rpc += 1
			self.mlim -= 1
			if self.mlim < 0:
				raise Exception("exceeded mlim")
	
	def parse(self, bs, rpc=None, mpc=None, mlim=None):
		if not mpc:
			mpc = self.mpc
		if not rpc:
			rpc = self.rpc
		if not mlim:
			mlim = self.mlim
		irpc = rpc
		
		if len(self.mem) < rpc+mlim:
			self.mem += [0 for i in xrange(rpc+mlim-len(self.mem))]
		lintab = bs.replace("\r\n","\n").replace("\r","\n").split("\n")
		
		for l in lintab:
			s = l[:].upper()
			while s.startswith(" ") or s.startswith("\t"):
				s = s[1:]
			while s.endswith(" ") or s.endswith("\t"):
				s = s[:-1]
			
			if s.startswith("@"): # label
				lbl,_,s = s[1:].partition(" ")
				if lbl in self.labels:
					raise Exception("duplicate label: "+lbl)
				self.labels[lbl] = mpc
			if not s:
				continue
			
			opc,_,param = s.partition(" ")
			pv = 0
			pt = ""
			if param:
				pv,pt = self.decparam(param)
			
			islabel = (type(pv) == type(""))
			issmall = False
			if islabel:
				issmall = pv.startswith("<") or pv.startswith(">")
			
			if pt == "zp":
				if opc+":rel" in OPTAB:
					pt = "rel"
				elif not issmall and (islabel or pv > 0xFF):
					if opc+":abs" in OPTAB:
						pt = "abs"
					else:
						raise Exception("value too large for zp")
			elif pt == "zpx":
				if not issmall and (islabel or pv > 0xFF):
					if opc+":abx" in OPTAB:
						pt = "abx"
					else:
						raise Exception("value too large for zpx")
			elif pt == "zpy":
				if not issmall and (islabel or pv > 0xFF):
					if opc+":aby" in OPTAB:
						pt = "aby"
					else:
						raise Exception("value too large for zpy")
			elif pt in ["izx","izy"]:
				if not issmall and (islabel or pv > 0xFF):
					raise Exception("value too large for "+pt)
			
			if islabel:
				print "%04X: %3s %3s @%s" % (mpc, opc, pt, pv)
			else:
				print "%04X: %3s %3s %04X" % (mpc, opc, pt, pv)
			
			op = OPTAB[opc+":"+pt]
			self.mem[rpc] = op['index']
			rpc += 1
			mpc += 1
			mlim -= 1
			if mlim < 0:
				raise Exception("exceeded mlim")
			
			if islabel:
				self.labrefs.append([pv,pt,rpc,mpc])
				pv = 0
			
			if pt:
				self.mem[rpc] += pv & 0xFF
				rpc += 1
				mpc += 1
				mlim -= 1
				if mlim < 0:
					raise Exception("exceeded mlim")
				if pt in ["abs","abx","aby","ind"]:
					self.mem[rpc] += (pv >> 8) & 0xFF
					rpc += 1
					mpc += 1
					mlim -= 1
					if mlim < 0:
						raise Exception("exceeded mlim")
		
		self.rpc = rpc
		self.mpc = mpc
		self.mlim = mlim
	
	def parseparam(self,param):
		if param.startswith("$"):
			return eval("0x"+param[1:])
		elif param.startswith("%"):
			v = 0
			for c in param[1:]:
				v <<= 1
				if c == '1':
					v |= 1
				elif c != '0':
					raise Exception("invalid bin digit")
			return v
		elif param.startswith("@"):
			return param[1:]
		else:
			return int(param)
	
	def decparam(self,param):
		if param.startswith("#"): # imm: immediate
			return self.parseparam(param[1:]),"imm"
		elif param.startswith("(") and param.endswith(")"):
			return self.parseparam(param[1:-3]),"ind"
		elif param.startswith("(") and param.endswith(",X)"):
			return self.parseparam(param[1:-3]),"izx"
		elif param.startswith("(") and param.endswith("),Y"):
			return self.parseparam(param[1:-3]),"izy"
		elif param.endswith(",X"):
			return self.parseparam(param[:-2]),"zpx"
		elif param.endswith(",Y"):
			return self.parseparam(param[:-2]),"zpy"
		else:
			return self.parseparam(param),"zp"
	
	def clipstr32b(self, s):
		s = s[:]
		if len(s) > 32:
			s = s[:32]
		while len(s) < 32:
			s += " "
		return s
	
	def save_nsf(self,fname,info):
		fp = open(fname,"wb")
		fp.write("NESM\x1A\x01")
		fp.write(chr(info['songcount']))
		fp.write(chr(info['songstart']))
		fp.write(struct.pack("<HHH",self.labels["_NSF_LOAD"],self.labels["_NSF_INIT"],self.labels["_NSF_PLAY"]))
		fp.write(self.clipstr32b(info['name']))
		fp.write(self.clipstr32b(info['author']))
		fp.write(self.clipstr32b(info['copyright']))
		fp.write(struct.pack("<H",info['speedntsc']))
		for v in info['banks']:
			fp.write(chr(v))
		fp.write(struct.pack("<HBB",info['speedpal'],info['palntsc'],info['extensions']))
		fp.write("\x00"*4)
		for v in self.mem:
			fp.write(chr(v))
		fp.close()

if __name__ == "__main__":
	print "Making test nsf"
	
	import pychip
	
	asm = pychip.Asm6502(0x00000,0x8000,0x1000)
	asm.parse("""
	@_nsf_load
		rts
	@_nsf_init
		lda #$00
		sta $02
		lda #$0C
		sta $03
	@np_rstctr
		lda #$09
		sta $04
		rts
	@_nsf_play
		dec $04
		beq @np_go
		rts
	@np_go
		ldx $02
		lda @notetab,x
		sta $4002
		lda @notetab2,x
		sta $4006
		lda @notetab3,x
		sta $400A
		inx
		lda @notetab,x
		sta $4003
		lda @notetab2,x
		sta $4007
		lda @notetab3,x
		sta $400B
		inx
		lda #%10100010
		lda #%10110010
		sta $4000
		sta $4004
		lda #%11000000
		sta $4008
		stx $02
		dec $03
		beq @_nsf_init
		jmp @np_rstctr
	""")
	
	xtb = [
		0x8000|int(pychip.CLK_PAL/((2.0**((i+3.0)/12.0))*880.0*2.0*16.0)+1) for i in xrange(12)
	]
	asm.binary(struct.pack("<"+"H"*12,*xtb),256,"notetab")
	asm.binary(struct.pack("<"+"H"*12,*(xtb[4:]+xtb[:4])),256,"notetab2")
	asm.binary(struct.pack("<"+"H"*12,*(xtb[8:]+xtb[:8])),256,"notetab3")
	asm.store_labels()
	asm.save_nsf("test.nsf",{
		'songcount': 1,
		'songstart': 1,
		'name': "pychip test",
		'author': "GreaseMonkey",
		'copyright': "2010, PD",
		'banks': [0,1,2,3,4,5,6,7],
		'speedntsc': 0x441A,
		'speedpal': 0x4E20,
		'palntsc': 0x01,
		'extensions': 0x00,
	})
