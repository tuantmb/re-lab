# Copyright (C) 2007-2010,	Valek Filippov (frob@df.ru)
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of version 3 or later of the GNU General Public
# License as published by the Free Software Foundation.
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301
# USA
#

import binascii
import sys,struct
import gtk
import tree
import hexdump
import pubblock
import ctypes
from utils import *

class PublisherContentDoc():
	def __init__(self,page,parent):
		self.parent=parent
		self.version = 1
		if page != None:
			self.page = page
			self.version = page.version
		self.pub98_types = {
			0:"Text",0x1:"Table",0x2:"Image",0x3:"OLE", 0x4:"Line",0x5:"Rect",0x6:"Shape",0x7:"Ellipse",
			0x8:"Text block",0xa:"Table",0xb:"Bookmark",0xf:"Group",
			0x13:"Style",
			0x14:"Page",0x15:"Document",0x1e:"Font",0x1f:"Art",
			0x21:"ImgData",0x22:"OleData",
			0x26:"Styles",0x28:"(pub2k3 0x4a)",0x29:"Printers",
			0x47:"ColorSchemes",
			0x54:"Filename"
		}
		self.pub98_ids = {
			"cnthdr":self.pubheader,
			"cnthdr98":self.pub98header,
			"txthdr98":self.pub98textheader,
			"zone2":self.pub98zone2,
			"proplim0-98":self.pub98proplim,
			"proplim1-98":self.pub98proplim,
			"proplim2-98":self.pub98proplim,
			"proplim3-98":self.pub98proplim,
			"Block0":self.pub98shape,
			"Block1":self.pub98shape,
			"Block2":self.pub98shape,
			"Block3":self.pub98shape,
			"Block4":self.pub98shape,
			"Block5":self.pub98shape,
			"Block6":self.pub98shape,
			"Block7":self.pub98shape,
			"Block8":self.pub98shape,
			"Blocke":self.pub98shape,
			"Blockf":self.pub98shape,
			"Block15":self.pub98doc,
			"BlockData1":self.pub98idlist, # size 14
			"BlockDatae":self.pub98idlist,
			"BlockDataf":self.pub98idlist,
			"BlockData13":self.pub98ptrlistheader, # first name, second char style, third para style
			"BlockData14":self.pub98idlist,
			"BlockData15":self.pub98idlist,
			"BlockData1e":self.pub98ptrlistheader,
			"BlockData1f":self.pub98ptrlistheader,
			# Data21: wmf
			"BlockData22":self.pub98oleData,
			"BlockData23":self.pub98ptrlistheader,
			"BlockData28":self.pub98cstlist,
			"BlockData29":self.pub98ptrlistheader,
			"BlockData2a":self.pub98ptrlistheader,
			"BlockData2b":self.pub98ptrlistheader,
			"BlockData2c":self.pub98idlist, # with data size=6
			"BlockData32":self.pub98ptrlistheader,
			"BlockData34":self.pub98cstlist,
			"BlockData43":self.pub98idlist,
			"BlockData47":self.pub98idlist, # with data size=4
		}

	def checkFinish(self,hd,data,off,name):
		if len(data)>off:
			extra=len(data)-off
			add_iter (hd,"##extra",binascii.hexlify(data[off:off+extra]), off, extra, "txt")
			print "%s: Find unexpected data"%name

	def pub98zhdr (self, hd,size,data):
		off=0
		typ=struct.unpack("<H",data[off:off+2])[0]
		add_iter(hd,"type",typ,off,2,"<H")
		off+=2
		for i in range(2):
			add_iter(hd,"decal[%d]"%i,ord(data[off]),off,1,"<B")
			off+=1
		return (typ,off)

	def pub98shape (self,hd,size,data):
		typ,off=self.pub98zhdr(hd,size,data)
		if self.contentVersion>=300:
			add_iter(hd,"rot",struct.unpack("<H",data[off:off+2])[0],off,2,"<H")
			off+=2
		what=["Xs","Ys","Xe","Ye"]
		for i in range(4):
			add_iter(hd,what[i],struct.unpack("<i",data[off:off+4])[0]/12700.,off,4,"<I")
			off+=4
		if self.contentVersion<300:
			add_iter(hd,"fl","%x"%struct.unpack("<H",data[off:off+2])[0],off,2,"<H")
			off+=2
			if typ>=0xe: # group have no style
				return
			for i in range(2): # col0=first color,col1=background
				val=struct.unpack('<B', data[off:off+1])[0]
				add_iter (hd,"col%d"%i,val,off,1,'<B')
				off+=1
			val=struct.unpack('<B', data[off:off+1])[0]
			add_iter (hd,"pattern",val,off,1,'<B')
			off+=1
			add_iter (hd,"col[line]",struct.unpack('<B', data[off:off+1])[0],off,1,'<B') # patternline
			off+=1
			add_iter (hd,"width[line]",struct.unpack('<B', data[off:off+1])[0],off,1,'<B')
			off+=1
			add_iter (hd,"f0",struct.unpack('<h', data[off:off+2])[0],off,2,'<H') # 0
			off+=2
			if typ==6:
				add_iter (hd,"shape[id]",struct.unpack('<H', data[off:off+2])[0],off,2,'<H')
				off+=2
				# 4 means rot90, c means rot 270
				add_iter (hd,"flags","%x"%struct.unpack('<H', data[off:off+2])[0],off,2,'<H')
				off+=2
				for i in range(4):
					add_iter (hd,"coord%d"%i,struct.unpack('<h', data[off:off+2])[0],off,2,'<h')
					off+=2
			elif typ<=3 or typ==5:
				add_iter (hd,"art[pictId]",struct.unpack('<h', data[off:off+2])[0],off,2,'<H')
				off+=2
				add_iter (hd,"width[unkn]",struct.unpack('<B', data[off:off+1])[0],off,1,'<B')
				off+=1
				for i in range(3):
					add_iter (hd,"col[line%d]"%(i+1),struct.unpack('<B', data[off:off+1])[0],off,1,'<B')
					off+=1
					add_iter (hd,"width[line%d]"%(i+1),struct.unpack('<B', data[off:off+1])[0],off,1,'<B')
					off+=1
				if typ<=1:
					strs=""
					for i in range(4):
						strs+=("%d,"%struct.unpack('<h', data[off:off+2])[0])
						off+=2
					add_iter(hd,"margins",strs,off-8,8,"txt")
					add_iter(hd,"text[id]",struct.unpack('<H', data[off:off+2])[0],off,2,'<H')
					off+=2
					if typ==1:
						add_iter (hd,"f1",struct.unpack('<h', data[off:off+2])[0],off,2,'<H') # e
						off+=2
						add_iter (hd,"num[col]",struct.unpack('<h', data[off:off+2])[0],off,2,'<H')
						off+=2
						add_iter (hd,"num[row]",struct.unpack('<h', data[off:off+2])[0],off,2,'<H')
						off+=2
						for i in range(2):
							add_iter(hd,"width" if i==0 else "height",struct.unpack("<i",data[off:off+4])[0]/12700.,off,4,"<I")
							off+=4

		if off<len(data):
			add_iter (hd,"extra",binascii.hexlify(data[off:len(data)]), off, len(data)-off, "txt")

	def pub98doc (self,hd,size,data):
		add_iter(hd,"Width",struct.unpack("<I",data[0x14:0x18])[0]/12700.,0x14,4,"<I")
		add_iter(hd,"Height",struct.unpack("<I",data[0x18:0x1c])[0]/12700.,0x18,4,"<I")
	def pub98oleData (self,hd,size,data):
		off=0
		add_iter(hd,"val",unicode(data[off:off+2],"cp1250"),off,2,'txt') # MO
		off+=2
		add_iter (hd,"id",struct.unpack('<H', data[off:off+2])[0],off,2,'<H')
		off+=2
		for i in range(2):
			add_iter (hd,"f%d"%i,struct.unpack('<H', data[off:off+2])[0],off,2,'<H')
			off+=2
	def pub98header(self,hd,size,data):
		off=2
		val=struct.unpack('<H', data[off:off+2])[0]
		add_iter (hd,"header[sz]","%02x"%val,off,2,'<H')
		off+=2
		add_iter(hd,"vers",struct.unpack("<H",data[off:off+2])[0],off,2,"<H") # 200 or 300
		off+=2 # v2:5f03 v8: 105 v200:a04
		add_iter(hd,"f0","%02x"%struct.unpack("<H",data[off:off+2])[0],off,2,"<H")
		off+=2
		pos=struct.unpack('<I', data[off:off+4])[0]
		add_iter(hd,"eof","%04x"%pos,off,4,'<I')
		off+=4
		for i in range(3): # v7: 2c0,114,134 ; v8?:7d,100,10a v9:268,16c,0
			val=struct.unpack('<H', data[off:off+2])[0]
			add_iter(hd,"f%d"%(i+2),"%02x"%val,off,2,'<H')
			off+=2

		names=["TextZone", "Blocks", "Zone2"];
		for i in range(3):
			pos=struct.unpack('<I', data[off:off+4])[0]
			off+=4
			if pos==0:
				continue
			add_iter(hd,names[i],"%04x"%pos,off-4,4,'<I')
		for i in range(2): # v7:100|100 or v9:500|500
			val=struct.unpack('<H', data[off:off+2])[0]
			add_iter(hd,"g%d"%i,"%02x"%val,off,2,'<H')
			off+=2

	def pubheader (self,hd,size,data):
		if struct.unpack("<H",data[2:4])[0] == 0x2c:
			add_iter(hd,"Version",struct.unpack("<H",data[0x22:0x24])[0],0x22,2,"<H")
			add_iter(hd,"Saved by",struct.unpack("<H",data[0x24:0x26])[0],0x24,2,"<H")
			self.version=3

	def pub98textheader (self,hd,size,data):
		off=0
		add_iter(hd,"Version",struct.unpack("<H",data[off:off+2])[0],off,2,"<H")
		off+=2
		add_iter(hd,"hdr[size]",struct.unpack("<H",data[off:off+2])[0],off,2,"<H")
		off+=2
		for i in range(3): # 200, 512, 0
			add_iter(hd,"f%d"%i,struct.unpack("<H",data[off:off+2])[0],off,2,"<H")
			off+=2
		add_iter(hd,"eof","%04x"%struct.unpack("<I",data[off:off+4])[0],off,4,'<I')
		off+=4
		add_iter(hd,"txt[pos]","%04x"%struct.unpack("<I",data[off:off+4])[0],off,4,'<I')
		off+=4
		add_iter(hd,"txt[end,pos]","%04x"%struct.unpack("<I",data[off:off+4])[0],off,4,'<I')
		off+=4
		for i in range(4):
			add_iter (hd,"index%d"%i,struct.unpack('<H', data[off:off+2])[0],off,2,'<H')
			off+=2
		for i in range(4):
			pos=struct.unpack('<I', data[off:off+4])[0]
			off+=4
			if pos==0:
				continue
			add_iter(hd,"Proplim%d[pos]"%i,"%04x"%pos,off-4,4,'<I')
	def pub98proplim (self,hd,size,data):
		off=0
		for i in range(2): # 1d, 404
			add_iter(hd,"f%d"%i,struct.unpack("<H",data[off:off+2])[0],off,2,"<H")
			off+=2
		N=struct.unpack('<H', data[off:off+2])[0]
		add_iter (hd,"N",N,off,2,'<H')
		off+=2
		add_iter (hd,"N[max]",struct.unpack('<H', data[off:off+2])[0],off,2,'<H')
		off+=2
		dataSz=struct.unpack('<H', data[off:off+2])[0] # 2
		add_iter (hd,"data[sz]",dataSz,off,2,'<H')
		off+=2
		for i in range(6): # 0|1,0,0,0,0,0
			add_iter (hd,"g%d"%i,struct.unpack('<H', data[off:off+2])[0],off,2,'<H')
			off+=2
		pos=struct.unpack('<I', data[off:off+4])[0]
		add_iter(hd,"pos[text]","%04x"%pos,off,4,'<I')
		off+=4
		if N==0:
			return
		str=""
		for i in range(N):
			pos=struct.unpack('<I', data[off:off+4])[0]
			off+=4
			str += ("%04x,"%pos)
		add_iter (hd,"pos[char]",str,off-4*N,4*N,'txt')
		for i in range(N): # index and flag?
			add_iter (hd,"index%d"%i,binascii.hexlify(data[off:off+dataSz]),off,dataSz,"text")
			off+=dataSz

	def pub98listheader (self,hd,size,data,ptrSize=None):
		if ptrSize==None:
			ptrSize=4 if self.version>1 else 2
		ptrType='<I' if ptrSize==4 else '<H'
		off=0
		N=struct.unpack(ptrType, data[off:off+ptrSize])[0]
		add_iter(hd,"N",N,off,ptrSize,ptrType)
		off+=ptrSize
		add_iter(hd,"N[max]",struct.unpack(ptrType, data[off:off+ptrSize])[0],off,ptrSize,ptrType)
		off+=ptrSize
		dataSize=struct.unpack(ptrType, data[off:off+ptrSize])[0]
		add_iter(hd,"data[sz]",dataSize,off,ptrSize,ptrType)
		off+=ptrSize
		for i in range(2): # 0 0
			add_iter(hd,"f%d"%i,struct.unpack("<h",data[off:off+2])[0],off,2,"<h")
			off+=2
		if ptrSize==4:
			add_iter(hd,"f2",struct.unpack("<h", data[off:off+2])[0],off,2,"<h")
			off+=2
		return (off,N,dataSize)

	def pub98ptrlistheader (self,hd,size,data):
		off,N,lastPtr=self.pub98listheader (hd,size,data)
		if off+(4 if self.version>1 else 2)*(N+1)>len(data):
			add_iter (hd,"data0###",binascii.hexlify(data[off:len(data)]),len(data)-off,"text")
			return
		zones=[]
		strs=""
		begOff=off
		for i in range(N+1):
			if self.version>1:
				ptr=struct.unpack("<I", data[off:off+4])[0]
				off+=4
			else:
				ptr=struct.unpack("<H", data[off:off+2])[0]
				off+=2
			strs += ("%2x,"%ptr)
			zones.append(ptr)
		add_iter (hd,"ptrs", strs, begOff, 4*(N+1) if self.version>1 else 2*(N+1), "txt")
		for i in range(N):
			if zones[i+1]<=zones[i]:
				continue
			add_iter (hd,"data%x"%zones[i],binascii.hexlify(data[begOff+zones[i]:begOff+zones[i+1]]),begOff+zones[i],zones[i+1]-zones[i],"text")
	def pub98cstlist (self,hd,size,data,ptrSize=None):
		off,N,dataSize=self.pub98listheader(hd,size,data,ptrSize)
		if off+dataSize*N>len(data):
			add_iter (hd,"data0###",binascii.hexlify(data[off:len(data)]),len(data)-off,"text")
			return
		if dataSize==2:
			for i in range(N):
				add_iter(hd,"ID%d"%i,"%2x"%struct.unpack("<H",data[off:off+2])[0],off,2,"<H")
				off+=2
		elif dataSize>0:
			for i in range(N):
				add_iter(hd,"data%d"%i,binascii.hexlify(data[off:off+dataSize]),off,dataSize,"<H")
				off+=dataSize
		self.checkFinish(hd,data,off,"cstlist")
	def pub98idlist(self,hd,size,data):
		self.pub98cstlist(hd,size,data,2)

	def pub98zone2 (self,hd,size,data):
		add_iter (hd,"data",binascii.hexlify(data),0,len(data),"text")

	# parse fdpc/fdpp-like blocks in pub97
	def parse97prop(self,page,data,parent,prop,pid):
		off = prop*0x200 # probably need to read block size in pub97qu
		num = ord(data[off+0x1ff])
		propiter = add_pgiter(page,"prop%s %s"%(pid,prop),"pub97","prop",data[off:off+0x200],parent)
		seenOffset={10000000}
		for i in range(num+1):
			ch = struct.unpack("<I",data[off+i*4:off+i*4+4])[0]
			t = ord(data[off+num*4+4+i])
			if t == 0:
				str = "default"
			elif t<num*2+2:
				str = "none"
			else:
				str = "[%02x]"%t
			add_pgiter(page,"Offset: %02x Style: %s"%(ch,str),"pub97","prop",data[off+i*4:off+i*4+4],propiter)
			if t == 0 or t<num*2+2 or t in seenOffset:
				continue;
			seenOffset.add(t)
		for t in sorted(seenOffset):
			if t>0xff:
				break
			l=ord(data[off+2*t])
			if pid=="1":
				l=2*l+1
			add_pgiter(page,"Style [%02x] "%t,"pub97","style"+pid,data[off+2*t:off+2*t+1+l],propiter)

	# parse "Quill"-like part in pub97
	# it's near empty in pub98
	def parse97qu (self,page,data,parent):
		off = struct.unpack("<I",data[0x12:0x16])[0]
		txtiter = add_pgiter (page,"TextZone","pub98","txtZONE","",parent)

		quhdr_size = struct.unpack("<H",data[off+2:off+4])[0]
		hditer = add_pgiter (page,"header","pub98","txthdr98",data[off:off+quhdr_size],txtiter)
		off += 10
		endzone = struct.unpack("<I",data[off:off+4])[0]
		off += 4
		txtstart = struct.unpack("<I",data[off:off+4])[0]
		off += 4
		if txtstart == endzone:
			# pub98
			self.version=2
			return
		txtend = struct.unpack("<I",data[off:off+4])[0]
		off += 4
		add_pgiter(page,"TEXT","pub","txt",data[txtstart:txtend],txtiter)
		index=[]
		for i in range(4):
			ptr=struct.unpack('<H', data[off:off+2])[0]
			off+=2
			index.append(ptr)
		for i in range(3):
			for j in range(index[i],index[i+1]):
				self.parse97prop(page,data,txtiter,j,"%d"%i)
		subZone=[]
		for i in range(4):
			pos=struct.unpack('<I', data[off:off+4])[0]
			off+=4
			if pos==0:
				continue
			subZone.append(("propLim%d"%i,"proplim%d-98"%i,pos))
		subZone.append(("EOF","EOF",endzone))
		listZone=list(sorted(subZone, key=lambda i: i[2]))
		for i in range(len(listZone)-1):
			subName,subType,subOff=listZone[i]
			add_pgiter(page,subName,"pub98",subType,data[subOff:listZone[i+1][2]],txtiter)

	def parse98zones (self,data,endblock):
		tr_start = struct.unpack("<I",data[0x16:0x1a])[0]
		blocks = {}
		reorder = []
		n_blocks = struct.unpack("<H",data[tr_start:tr_start+2])[0]
		tr_end = tr_start + n_blocks*10+2
		tr_iter = add_pgiter (self.page,"Blocks","pub",0,data[tr_start:tr_end],self.parent)
		block_c_end = struct.unpack("<I",data[tr_start+18:tr_start+22])[0]
		add_pgiter (self.page,"Num of blocks (%02x)"%n_blocks,"pub",0,data[tr_start:tr_start+2],tr_iter)
		off = tr_start+2
		for i in range(n_blocks):
			fmt1 = ord(data[off+i*10])
			fmt2 = ord(data[off+i*10+1])
			blk_id = struct.unpack("<H",data[off+i*10+2:off+i*10+4])[0]
			par_id = struct.unpack("<H",data[off+i*10+4:off+i*10+6])[0]
			blk_offset = struct.unpack("<I",data[off+i*10+6:off+i*10+10])[0]
			add_pgiter (self.page,"Ptr %02x\t[Fmt: %02x %02x ID: %02x Parent: %02x Offset: %02x]"%(i,fmt1,fmt2,blk_id,par_id,blk_offset),"pub",0,data[off+i*10:off+i*10+10],tr_iter)
			blocks[blk_id] = [blk_offset,par_id]
			reorder.append(blk_id)
			if i > 0:
				blocks[prev_id].append(blk_offset)
			prev_id = blk_id

		blocks[prev_id].append(endblock)
		p_iter=tr_iter
		for i in reorder:
			start = blocks[i][0]
			end = blocks[i][2]
			par = blocks[i][1]
			b_type = struct.unpack("<H",data[start:start+2])[0]
			decal=ord(data[start+3])
			if self.pub98_types.has_key(b_type):
				b_txt = self.pub98_types[b_type]
			else:
				b_txt = "%02x"%b_type
			if blocks.has_key(par):
				p_iter = blocks[par][3]
			if decal!=0 and start+decal<end:
				add_pgiter (self.page,"BlockData %02x (%s)"%(i,b_txt),"pub98","BlockData%x"%b_type,data[start+decal:end],p_iter)
				end=start+decal
			blocks[i].append(add_pgiter (self.page,"Block %02x (%s)"%(i,b_txt),"pub98","Block%x"%b_type,data[start:end],p_iter))

	# parse "Contents" part of the pub98/pub2k
	def parse98 (self,data):
		self.contentVersion=struct.unpack("<H",data[4:4+2])[0]
		zones=[]
		zones.append((0,struct.unpack("<I",data[8:8+4])[0]))
		off=0x12
		for i in range(3):
			zones.append((i,struct.unpack("<I",data[off:off+4])[0]))
			off+=4
		add_pgiter (self.page,"Header","pub","cnthdr98",data[:0x22],self.parent)
		self.parse97qu(self.page,data,self.parent) # zone 0
		listZone=list(sorted(zones, key=lambda i: i[1]))
		for i in range(len(listZone)-1):
			if listZone[i][0]==2:
				add_pgiter (self.page,"Zone2","pub98","zone2",data[listZone[i][1]:listZone[i+1][1]],self.parent)
			elif listZone[i][0]==1:
				self.parse98zones(data,listZone[i+1][1])

	# parse "Contents" part of the OLE container
	def parse(self,data):
		model = self.page.model
		hdrsize = struct.unpack("<H",data[2:4])[0]
		if hdrsize == 0x22:
			self.parse98 (data)
			return
		add_pgiter (self.page,"Header","pub","cnthdr",data[0:hdrsize],self.parent)
		blocks = {}
		reorders = []
		off = hdrsize
		# Parse the 1st block after header
		[dlen] = struct.unpack('<I', data[off:off+4])
		iter1 = add_pgiter (self.page,"Block A [%02x]"%off,"pub",0,data[off:off+dlen],self.parent)
		pubblock.parse (self.page,data[off+4:off+dlen],iter1,0)
		# Parse the dummy list block (the 2nd after header)
		[off] = struct.unpack('<I', data[0x1e:0x22])
		[dlen] = struct.unpack('<I', data[off:off+4])
		iter1 = add_pgiter (self.page,"Block B [%02x]"%off,"pub",0,data[off:off+dlen],self.parent)
		pubblock.parse (self.page,data[off+4:off+dlen],iter1,1)
		# Parse the list of blocks block
		off = struct.unpack('<I', data[0x1a:0x1e])[0]
		[dlen] = struct.unpack('<I', data[off:off+4])
		iter1 = add_pgiter (self.page,"Trailer [%02x]"%off,"pub",0,data[off:off+dlen],self.parent)
		pubblock.parse (self.page,data[off+4:off+dlen],iter1,2)
		list_iter = model.iter_nth_child(iter1,2)
		j = 255
		name = "***"
		for k in range (model.iter_n_children(list_iter)):
			# print "Parse 'Contents' block %02x"%k
			curiter = model.iter_nth_child(list_iter,k)
			test = model.get_value(curiter,0)
			if test[len(test)-4:] != "ID78":
				opts = ""
				parid = None
				for i in range (model.iter_n_children(curiter)):
					child = model.iter_nth_child(curiter,i)
					id = model.get_value(child,0)[4:6]
					if id == "02":
						type = struct.unpack("<H",model.get_value(child,3))[0]
					if id == "04":
						offset = struct.unpack("<I",model.get_value(child,3))[0]
					if id == "05":
						[parid] = struct.unpack("<I",model.get_value(child,3))
				dlen = struct.unpack('<I', data[offset:offset+4])[0]
				if parid != None:
					if blocks.has_key(parid):
						if pubblock.block_types.has_key(type):
							name = "(%02x) %s"%(j,pubblock.block_types[type])
						else:
							name = "(%02x) Type: %02x"%(j,type)
						iter1 = add_pgiter (self.page,name,"pub",0,data[offset:offset+dlen],blocks[parid])
						pubblock.parse (self.page,data[offset+4:offset+dlen],iter1,i+3,-1,type)
						blocks[k+255] = iter1
					else:
						reorders.append(k+255)
				else:
					if pubblock.block_types.has_key(type):
						name = "(%02x) %s"%(j,pubblock.block_types[type])
					else:
						name = "(%02x) Type: %02x"%(j,type)
					iter1 = add_pgiter (self.page,name,"pub",0,data[offset:offset+dlen],self.parent)
					pubblock.parse (self.page,data[offset+4:offset+dlen],iter1,i+3)
					blocks[k+255] = iter1
			j += 1

def collect_ec(model,parent):
	res = ""
	value = model.get_value(parent,3)
	if model.iter_n_children(parent):
		res += value[:8]
		for i in range(model.iter_n_children(parent)):
			citer = model.iter_nth_child(parent, i)
			res += collect_ec(model,citer)
	else:
		res += value
	return res

def collect_escher(model,citer):
	res = ""
	tmp = ""
	for i in range(model.iter_n_children(citer)):
		gciter = model.iter_nth_child(citer, i)
		name = model.get_value(gciter,0)
		value = model.get_value(gciter,3)
		res += value[:8]
		tmp += value
		for j in range(model.iter_n_children(gciter)):
			ggciter = model.iter_nth_child(gciter, j)
			res += collect_ec(model,ggciter)

		if len(res) < len(tmp):
			res += tmp[len(res):]

	return res

def dump_tree (model, parent, outfile,cgsf):
	ntype = model.get_value(parent,1)
	name = model.get_value(parent,0)
	value = model.get_value(parent,3)

	if name == 'Quill':
		child = cgsf.gsf_outfile_new_child(outfile,name,1)
		cgsf.gsf_output_write (child,len(value),value)
		citer = model.iter_nth_child(parent, 0)
		gname = model.get_value(citer,0)
		gvalue = model.get_value(citer,3)
		gchild = cgsf.gsf_outfile_new_child(child,gname,1)
		cgsf.gsf_output_write (gchild,len(gvalue),gvalue)
		for i in range(model.iter_n_children(citer)):
			gciter = model.iter_nth_child(citer, i)
			ggname = model.get_value(gciter,0)
			ggvalue = model.get_value(gciter,3)
			ggchild = cgsf.gsf_outfile_new_child(gchild,ggname,0)
			cgsf.gsf_output_write (ggchild,len(ggvalue),ggvalue)
			cgsf.gsf_output_close (ggchild)
		cgsf.gsf_output_close (gchild)

	elif name =="Escher":
		child = cgsf.gsf_outfile_new_child(outfile,name,1)
		cgsf.gsf_output_write (child,len(value),value)
		for i in range(model.iter_n_children(parent)):
			citer = model.iter_nth_child(parent, i)
			name = model.get_value(citer,0)
			if name == "EscherStm":
				value = collect_escher(model,citer)
			else:
				value = model.get_value(citer,3)
			gchild = cgsf.gsf_outfile_new_child(child,name,0)
			cgsf.gsf_output_write (gchild,len(value),value)
			cgsf.gsf_output_close (gchild)

	else: # Quill/Escher
		child = cgsf.gsf_outfile_new_child(outfile,name,0)
		cgsf.gsf_output_write (child,len(value),value)

	cgsf.gsf_output_close (child)


def save (page, fname):
	model = page.view.get_model()
	cgsf = ctypes.cdll.LoadLibrary('libgsf-1.so')
	cgsf.gsf_init()
	output = cgsf.gsf_output_stdio_new (fname)
	outfile = cgsf.gsf_outfile_msole_new (output);
	iter1 = model.get_iter_first()
	while None != iter1:
		dump_tree(model, iter1, outfile,cgsf)
		iter1 = model.iter_next(iter1)
	cgsf.gsf_output_close(outfile)
	cgsf.gsf_shutdown()
