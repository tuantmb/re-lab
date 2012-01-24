#!/usr/bin/env python
# Copyright (C) 2011	Valek Filippov (frob@df.ru)
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

import gtk
import cairo
import struct

class HexView():
	def __init__(self,data=None,lines=[],comments={},offset=0):
		# UI related objects
		self.parent = None 						# used to pass info for status bar update (change to signal)
		self.hv = gtk.DrawingArea()		# middle column with the main hex context
		self.vadj = gtk.Adjustment(0.0, 0.0, 1.0, 1.0, 1.0, 1.0)
		self.hadj = gtk.Adjustment(0.0, 0.0, 1.0, 1.0, 1.0, 1.0)
		self.vs = gtk.VScrollbar(self.vadj)
		self.hs = gtk.HScrollbar(self.hadj)
		self.hbox1 = gtk.HBox()
		self.hbox2 = gtk.HBox()
		self.hbox3 = gtk.HBox()
		self.table = gtk.Table(3,4,False)
		self.table.attach(self.hv,0,3,0,2)
		self.table.attach(self.hbox1,0,1,2,3,0,0)
		self.table.attach(self.hs,1,2,2,3,gtk.EXPAND|gtk.FILL,0)
		self.table.attach(self.hbox2,2,3,2,3,0,0)
		self.table.attach(self.hbox3,3,4,0,1,0,0)
		self.table.attach(self.vs,3,4,1,2,0)

		# UI to insert comment
		self.ewin = gtk.Window(gtk.WINDOW_TOPLEVEL)
		self.ewin.connect ("focus-out-event", lambda d, r: d.hide())
		self.ewin.set_resizable(True)
		self.ewin.set_modal(False)
		self.ewin.set_decorated(False)
		self.ewin.set_border_width(0)
		self.entry = gtk.Entry()
		self.entry.connect("key-press-event",self.entry_key_pressed)
		self.ewin.add(self.entry)

		# variables to store things
		self.data = data				# data presented in the widget
		self.fname = ""					# to store filename
		self.offset = offset		# current cursor offset
		self.offnum = 0					# offset in lines
		self.tdx = -1						# width of one glyph
		self.tht = 0						# height of one glyph
		self.numtl = 0					# number of lines
		self.lines = lines			# offsets of lines in dump (offset,mode,comment idx)
		self.comments = comments	# hash of offset:length/text
		self.keep_cmnt = 0			# to keep comment len
		self.maxaddr = 16				# current length of the longest line
		self.hvlines = []				# cached text of lines
		self.selr = None
		self.selc = None
		self.drag = 0						# flag to track if we drag something
		self.kdrag = 0					# flag to reinit selection if shift was released/pressed
		self.curr = 0						# current row
		self.curc = 0						# current column
		self.mode = ""					# flag to jump to the current scrollbar offset or scroll back to hv cursor
		self.prer = 0						# previous row
		self.prec = 0						# previous column
		self.shift = 0
		self.sel = None					# to keep current selection (rs,cs,re,ce)
		self.mtt = None					# mx, my, num -- to show how many bytes selected
		self.bklines = []				# previous state of the lines to support one step undo
		self.bkhvlines = []			# previous state of the hvlines to support one step undo
		self.exposed = 0
		self.debug = -1					# -1 -- debug off, 1 -- debug on
		
		# connect signals and call some init functions
		self.hv.set_can_focus(True)
		self.hv.set_app_paintable(True)
		self.hv.set_events(gtk.gdk.BUTTON_PRESS_MASK | gtk.gdk.BUTTON_RELEASE_MASK | gtk.gdk.POINTER_MOTION_MASK)
		self.hv.connect("button_press_event",self.on_button_press)
		self.hv.connect("button_release_event",self.on_button_release)
		self.hv.connect ("key-press-event", self.on_key_press)
		self.hv.connect ("key-release-event", self.on_key_release)
		self.hv.connect("expose_event", self.expose)
		self.hv.connect("motion_notify_event",self.on_motion_notify)
		self.vadj.connect("value_changed", self.on_vadj_changed)

		# functions to handle kbd input
		self.okp = {65362:self.okp_up , 65365:self.okp_pgup, 65364:self.okp_down,
			65366:self.okp_pgdn, 65361:self.okp_left, 65363:self.okp_right,
			65360:self.okp_home, 65367:self.okp_end, 65535:self.okp_del,
			65288:self.okp_bksp, 65293:self.okp_enter,
			65289:self.okp_tab,
			65379:self.okp_ins,
			100:self.okp_d, # "d" for debug
			97:self.okp_selall, # ^A for 'select all'
			99:self.okp_copy, # ^C for 'copy'
			122:self.okp_undo, # ^Z for 'undo'
			105:self.okp_ins	# i for Insert
			}


		if lines == []:
			self.init_lines()				# init as a standard "all 0x10 wide" lines
		else:
			for i in range(len(lines)):
				self.hvlines.append("")
				self.bkhvlines.append("")
			self.set_maxaddr()

	def okp_tab(self,event):
		self.exposed = 0
		self.bklines = []
		self.bkhvlines = []
		self.bklines += self.lines
		self.bkhvlines += self.hvlines
		if self.curr >  0:
			# wrap at curc
			self.fmt(self.curr,[self.line_size(self.curr-1)])
			self.curr += 1
			self.prec = self.curc
			self.exposed = 1


	def okp_up(self,event):
		self.mode = "c"
		if self.offnum > 0 and self.curr < self.offnum+1:
			self.offnum -= 1
			self.mode = ""
		self.curr -= 1
		if self.curr < 0:
			self.curr = 0
		if self.curr > self.offnum + self.numtl:
			self.curr = self.offnum
		maxc = self.lines[self.curr+1][0] - self.lines[self.curr][0] -1
		if self.curc > maxc:
			self.curc = maxc
		return 1

	def okp_pgup(self,event):
		self.mode = "c"
		self.curr -= (self.numtl+3)
		if self.curr < 0:
			self.curr = 0
		if self.offnum > 0 and self.curr < self.offnum+1:
			self.offnum -= (self.numtl+3)
			self.mode = ""
		if self.offnum < 0:
			self.offnum = 0
		if self.curr > self.offnum + self.numtl:
			self.curr = self.offnum
		maxc = self.lines[self.curr+1][0] - self.lines[self.curr][0] -1
		if self.curc > maxc:
			self.curc = maxc
		return 1

	def okp_down(self,event):
		self.mode = "c"
		if self.offnum < len(self.lines)-self.numtl and self.curr >= self.offnum+self.numtl-3:
			self.offnum += 1
			self.mode = ""
		self.curr += 1
		if self.curr > len(self.lines)-2:
			self.curr = len(self.lines)-2
		if self.curr < self.offnum:
			self.curr = self.offnum
		maxc = self.lines[self.curr+1][0] - self.lines[self.curr][0] -1
		if self.curc > maxc:
			self.curc = maxc
		return 2

	def okp_pgdn(self,event):
		self.mode = "c"
		self.curr += (self.numtl+3)
		if self.curr > len(self.lines)-2:
			self.curr = len(self.lines)-2
		if self.offnum < len(self.lines)-self.numtl and self.curr >= self.offnum+self.numtl-3:
			self.offnum += (self.numtl+3)
			self.mode = ""
		if self.offnum > len(self.lines)-self.numtl:
			self.offnum = len(self.lines)-self.numtl
		if self.curr < self.offnum:
			self.curr = self.offnum
		maxc = self.lines[self.curr+1][0] - self.lines[self.curr][0] -1
		if self.curc > maxc:
			self.curc = maxc
		return 2

	def okp_left(self,event):
		self.mode = "c"
		self.curc -= 1
		if self.curc < 0:
			if self.curr > 0:
				self.curr -= 1
				self.curc = self.lines[self.curr+1][0] - self.lines[self.curr][0] -1
				self.mode = ""
			else:
				self.curc = 0
		self.shift = 1
		return 1

	def okp_right(self,event):
		self.mode = "c"
		self.curc += 1
		maxc = self.lines[self.curr+1][0] - self.lines[self.curr][0] -1
		if self.curc > maxc:
			if self.curr < len(self.lines)-2:
				self.curc = 0
				flag = 2
				if self.offnum < len(self.lines)-self.numtl and self.curr >= self.offnum+self.numtl-3:
					self.offnum += 1
				self.curr += 1
				if self.curr > len(self.lines)-2:
					self.curr = len(self.lines)-2
				if self.curr < self.offnum:
					self.curr = self.offnum
				self.mode = ""
			else:
				self.curc = maxc
		self.shift = -1
		return 1

	def okp_home(self,event):
		self.mode = "c"
		self.shift -= self.curc
		self.curc = 0
		if event.state == gtk.gdk.CONTROL_MASK:
			self.curr = 0
			self.offnum = 0
			self.mode = ""
		return 1

	def okp_end(self,event):
		self.mode = "c"
		self.shift = self.curc
		if event.state == gtk.gdk.CONTROL_MASK:
			self.curr = len(self.lines)-2
			self.offnum = len(self.lines)-self.numtl
			self.mode = ""
		self.curc = self.lines[self.curr+1][0] - self.lines[self.curr][0] -1
		if self.curc == -1:
			self.curc = 0
		return 2

	def okp_del(self,event):
		self.exposed = 0
		self.bklines = []
		self.bkhvlines = []
		self.bklines += self.lines
		self.bkhvlines += self.hvlines
		if self.curr != len(self.lines)-2: # not in the last row
				self.fmt(self.curr,[self.line_size(self.curr)+self.line_size(self.curr+1)])
				self.prec = self.curc - 1
				self.prer = self.curr - 1
				self.exposed = 1

	def okp_ins(self,event):
		xw,yw = self.hv.get_parent_window().get_position()
		xv,yv = self.hv.window.get_position()
		ys = yw+ yv+int((self.curr+0.5-self.offnum)*self.tht)
		xs = xw+xv+int((10+self.curc*3+4.5)*self.tdx)
		if self.lines[self.curr][1] > 1:
			if self.comments.has_key(self.lines[self.curr][2]):
				self.entry.set_text(self.comments[self.lines[self.curr][2]][1])
				cpos = self.lines[self.curr][0]+self.curc
				cstart = self.lines[self.curr][2]
				cend = cstart + self.comments[self.lines[self.curr][2]][0]
				if cpos >= cstart and cpos <= cend:
					self.keep_cmnt = 1
		self.ewin.show_all()
		self.ewin.move(xs,ys)

	def okp_selall(self,event):
		self.sel = 0,0,self.numtl,self.lines[self.numtl-1][0]

	def okp_copy(self,event):
			#FIXME: this doesn't work
			#	copy selection to clipboard
			clp = gtk.clipboard_get(gtk.gdk.SELECTION_CLIPBOARD)
			clp.set_text("test")

	def okp_undo(self,event):
		self.lines = self.bklines
		self.hvlines = self.bkhvlines
		self.set_maxaddr()
		self.exposed = 1

	def okp_bksp(self,event):
		# at start of the row it joins full row to the previous one
		# any other position -- join left part to the previous row
		self.exposed = 0
		self.bklines = []
		self.bkhvlines = []
		self.bklines += self.lines
		self.bkhvlines += self.hvlines
		if self.curr > 0:
			if self.curc == 0:
				#  join full row
				cc = self.line_size(self.curr-1)
				self.fmt(self.curr-1,[self.line_size(self.curr)+self.line_size(self.curr-1)])
				self.curc = cc
				self.curr -= 1
				self.prec = self.curc - 1
			else:
				# join part of the row
				self.fmt(self.curr-1,[self.curc+self.line_size(self.curr-1)])
				self.curc = 0
				self.prec = self.curc + 1
			self.exposed = 1

	def okp_enter(self,event):
		# split row, move everything right to the next (new) one pushing everything down
		self.exposed = 0
		self.bklines = []
		self.bkhvlines = []
		self.bklines += self.lines
		self.bkhvlines += self.hvlines
		if self.curr < len(self.lines)-1 and self.curc > 0:
			# wrap at curc
			self.fmt(self.curr,[self.curc])
			self.curc = 0
			self.curr += 1
			self.prec = self.curc - 1
		elif self.curr > 0 and self.curc == 0:
			# insert separator
			if self.lines[self.curr-1][1] == 0:
				self.lines[self.curr-1] = (self.lines[self.curr-1][0],1)
			elif self.lines[self.curr-1][1] == 2:
				self.lines[self.curr-1] = (self.lines[self.curr-1][0],3,self.lines[self.curr-1][2])
			self.exposed = 1

	def okp_d(self,event):
		self.debug *= -1

	def on_vadj_changed (self, vadj):
		# vertical scroll line
		if int(vadj.value) != self.offnum:
			self.offnum = int(vadj.value)
			self.vadj.upper = len(self.lines)-self.numtl+1
			self.hv.hide()
			self.hv.show()
		return True

	def set_dxdy(self):
		# calculate character extents
		ctx = self.hv.window.cairo_create()
		ctx.select_font_face("Monospace", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
		ctx.set_font_size(14)
		ctx.set_line_width(1)
		(xt, yt, wt, ht, dx, dy) = ctx.text_extents("o")
		x,y,width,height = self.hv.allocation
		self.tdx = int(dx)
		self.tht = int(ht+6)
		self.hbox1.set_size_request(self.tdx*9,0)
		self.hbox3.set_size_request(0,self.tht+4)
		self.vadj.upper = len(self.lines)-self.numtl+1
		self.vadj.value = self.offnum

	def init_lines(self):
		# set initial line lengths
		for i in range(len(self.data)/16+1):
			self.lines.append((i*16,0))
			self.hvlines.append("")
			self.bkhvlines.append("")
		self.lines.append((len(self.data),0))

	def set_maxaddr (self):
		# check and update maxaddr to the value of the longest line
		ma = 16
		for i in range(len(self.lines)-1):
			ta = self.lines[i+1][0]-self.lines[i][0]
			if ta > ma:
				ma = ta
		self.maxaddr = ma

	def cursor_in_sel(self):
		# checks if cursor is in the selection
		if self.sel == None:
			return 0
		elif self.curr > self.sel[2] or self.curr < self.sel[0]:
			return 0
		elif self.curr == self.sel[0] and self.curc < self.sel[1]:
			return 0
		elif self.curr == self.sel[2] and self.curc > self.sel[3]:
			return 0
		return 1

	def get_sel_len(self):
		# calculates length of selection
		rs,cs,re,ce = self.sel
		if rs == re:
			return ce-cs
		else:
			l = self.line_size(rs)-cs+ce
			for i in range(re-rs-1):
				l += self.line_size(rs+i)
			return l

	def get_sel_end(self,row,offset):
		# calulates r,c for the offset
		roff = self.lines[row+1][0]
		i = 0
		while offset > roff:
			i += 1
			roff = self.lines[row+i+1][0]
			if row+i == len(self.lines):
				break
				
		c = self.line_size(row+i)
		if roff + self.line_size(row+i) > offset:
			c += offset-roff
		return row+i,c-1

	def entry_key_pressed(self, entry, event):
		# inserting comment
		if event.keyval == 65307: # Esc
			self.ewin.hide()
			entry.set_text("")
		elif event.keyval == 65293: # Enter
			self.ewin.hide()
			cmnt_offset = self.lines[self.curr][0]+self.curc
			if entry.get_text():
				mode = self.lines[self.curr][1]
				if self.lines[self.curr][1] < 2:
					mode += 2
					old_coff = -1
				else:
					old_coff = self.lines[self.curr][2]

				if self.keep_cmnt:
					self.comments[self.lines[self.curr][2]] = (self.comments[self.lines[self.curr][2]][0],entry.get_text())
					self.keep_cmnt = 0
				else:
					s = 1
					if self.cursor_in_sel():
						for i in range(self.sel[2]-self.sel[0]-1):
							l = self.sel[0]+i+1
							self.lines[l] = (self.lines[l][0],0)
						l = self.sel[0]
						cmnt_offset = self.lines[self.sel[0]][0]+self.sel[1]
						self.lines[l] = (self.lines[l][0],2,cmnt_offset)
						s = self.get_sel_len()
					else:
						self.lines[self.curr] = (self.lines[self.curr][0],mode,cmnt_offset)
					self.comments[cmnt_offset] = (s,entry.get_text())	

					if old_coff != cmnt_offset:
						if self.comments.has_key(old_coff):
							del self.comments[old_coff]
			else:
				self.lines[self.curr] = (self.lines[self.curr][0],self.lines[self.curr][1]-2)
				if self.comments.has_key(cmnt_offset):
					del self.comments[cmnt_offset]

	def on_key_release (self, view, event):
		# part of the data selection from keyboard
		if event.keyval == 65505 or event.keyval == 65506:
			self.kdrag = 0
			self.mtt = None
			self.expose(view,event)

	def on_key_press (self, view, event):
		# handle keyboard input
		flag = 0
		self.exposed = 0
		self.mode = ""
		self.shift = 0
		self.prer = self.curr
		self.prec = self.curc
		if event.state == gtk.gdk.SHIFT_MASK:
			if self.kdrag == 0:
				self.sel = (self.curr,self.curc,self.curr,self.curc)
				self.kdrag = 1

		if self.okp.has_key(event.keyval):
			tmp = self.okp[event.keyval](event)
			if tmp:
				flag = tmp

		if self.curr < self.offnum:
			# Left/Right/BS/Enter 												 -- scroll back to cursor   (flag 0)
			# cursor upper than position and Up/PgUp/Home  -- scroll back to cursor   (flag 1)
			# cursor upper than position and Down/PgDn/End -- move cursor to position (flag 2)
			if flag < 2:
				self.offnum = self.curr
			else:
				self.curr = self.offnum
		elif self.curr > self.offnum+self.numtl:
			# Left/Right/BS/Enter 												 -- scroll back to cursor   (flag 0)
			# cursor lower than position and Down/PgDn/End -- scroll back to cursor   (flag 2)
			# cursor lower than position and Up/PgUp/Home  -- move cursor to position (flag 1)
			if flag != 1:
				self.offnum = self.curr
			else:
				self.curr = self.offnum

		if self.offnum > max(len(self.lines)-self.numtl,0):
			self.offnum = len(self.lines)-self.numtl



		if event.state == gtk.gdk.SHIFT_MASK:
			if self.sel != None:
				r1 = self.sel[0]
				r2 = self.sel[2]
				c1 = self.sel[1]
				c2 = self.sel[3]
				if self.curr == self.prer: # in the same line
					if r1 == r2:
						if self.curc > self.prec: # move right
							if c2 <= self.curc:
								c2 = self.curc+1
							else:
								c1 = self.curc
						else: # move left
							if c1 == self.prec:
								c1 = self.curc
							else:
								c2 = self.curc+1
					else:
						if self.curc > self.prec: # move right
							if self.curr == r2: # increase c2
								c2 = self.curc+1
							else:								# increase c1
								c1 = self.curc
						else:
							if self.curr == r2: # decrease c1
								c2 = self.curc+1
							else:								# decrease c2
								c1 = self.curc
				elif self.curr > self.prer: # move down
					if r2 == self.prer:
						r2 = self.curr
						c2 = self.curc+1
					else:
						r1 = self.curr
						c1 = self.curc
				else: # move up
					if r2 == self.prer and r1 != r2:
						r2 = self.curr
						c2 = self.curc+1
					else:
						if r2 <= self.curr:
							c = c2
							c = self.curc
							c1 = c
							r1 = self.curr
						else:
							r1 = self.curr
							c1 = self.curc

				self.sel = r1,c1,r2,c2
				self.mode = ""
				self.exposed = 1
				y = (r2-self.offnum+1.5)*self.tht # +1
				x = (self.curc*3+11.5)*self.tdx
				
				s = c2 - c1
				if r1 != r2:
					s = self.lines[r2][0] + c2 - self.lines[r1][0]-c1
				self.mtt = x,y,s
				self.parent.calc_status(self.data[self.lines[r1][0]+c1:self.lines[r2][0]+c2],s)


		self.vadj.upper = len(self.lines)-self.numtl+1
		self.vadj.value = self.offnum
		if self.curr != self.prer or self.curc != self.prec or self.exposed == 1:
			self.expose(view,event)

#		to quickly check what keyval value is for any new key I would like to add
#		print event.keyval,event.state

		return True

	def split_string(self, r = -1, c = -1):
		if r == -1:
			r = self.curr
		if c == -1:
			c = self.curc
		# helper to handle 'enter' and 'delete'
		if self.debug == 1:
			print "Upd",r,"(%02x)"%self.lines[r][0],self.line_size(r),c
		prehex,preasc = self.hvlines[r]
		lhex = prehex[:c*3]
		rhex = prehex[c*3:]
		lasc = preasc[:c]
		rasc = preasc[c:]
		self.hvlines[r] = lhex,lasc
		self.hvlines.insert(r+1,(rhex,rasc))
		if self.debug == 1:
			print "Upd2",r,"(%02x) and"%self.lines[r][0],r+1,"(%02x)"%self.lines[r+1][0]

	def line_size(self,row):
		# returns size of line or -1 if 'row' is behind
		# acceptable range
		if row < len(self.lines)-1:
			return self.lines[row+1][0]-self.lines[row][0]
		else:
			return 0

	def attach_next(self,row):
		# attach next line to one pointed by 'row'
		# and return 1
		# or 0 if 'row' is the last line or after
		if row < len(self.lines)-2:
			if self.lines[row+1][1] > 1:
				if self.lines[row][1] < 2:
					self.lines[row] = (self.lines[row][0],self.lines[row+1][1],self.lines[row+1][2])
			self.lines.pop(row+1)
			self.hvlines[row] = ""
			self.hvlines[row+1] = ""
			self.get_string(row)
			self.get_string(row+1)
			if self.debug == 1:
				print "Upd",row,"(%02x) and"%self.lines[row][0],row+1,"(%02x)"%self.lines[row+1][0]
			nh,na = self.hvlines[row]
			ph,pa = self.hvlines[row+1]
			self.hvlines[row] = nh+ph,na+pa
			self.hvlines.pop(row+1)
			return 1
		else:
			return 0

	def break_line(self,row,col):
		# breaks line 'row' at 'col' position
		# 'abcd' + col=0 -> a/bcd
		rs = self.line_size(row)
		if rs > 1 and col < rs-1:
			if self.lines[row][1] > 1:
				if self.lines[row][2] > self.lines[row][0]+col:
					self.lines.insert(row+1,(self.lines[row][0]+col+1,self.lines[row][1],self.lines[row][2]))
					self.lines[row] = (self.lines[row][0],0,None)
				else:
					mode = self.lines[row][1]
					cmnt = self.lines[row][2]
					self.lines[row] = (self.lines[row][0],2,cmnt)
					self.lines.insert(row+1,(self.lines[row][0]+col+1,mode-2,None))
			else:
				self.lines.insert(row+1,(self.lines[row][0]+col+1,self.lines[row][1]))
				if self.lines[row][1] == 1:
					self.lines[row] = (self.lines[row][0],0,None)

		if self.debug == 1:
			print "Upd",row,"(%02x)"%self.lines[row][0],self.line_size(row),col+1
		prehex,preasc = self.hvlines[row]
		lhex = prehex[:col*3+3]
		rhex = prehex[col*3+3:]
		lasc = preasc[:col+1]
		rasc = preasc[col+1:]
		self.hvlines[row] = lhex,lasc
		self.hvlines.insert(row+1,(rhex,rasc))
		if self.debug == 1:
			print "Upd2",row,"(%02x) and"%self.lines[row][0],row+1,"(%02x)"%self.lines[row+1][0]

	def fmt_row(self,row,cmd):
		for i in range(len(cmd)):
			rs = self.line_size(row+i)
			res = 1
			while rs <= int(cmd[i]) and res:
				res = self.attach_next(row+i)
				rs = self.line_size(row+i)
			if rs > int(cmd[i]):
				self.break_line(row+i,int(cmd[i])-1)

	def fmt(self,row,col):
		self.fmt_row(row, col)
		if row < len(self.hvlines)-1:
			self.hvlines[row+1] = ""
		self.set_maxaddr()
		self.tdx = -1 # force to recalculate in expose
		self.sel = None


	def on_button_release (self, widget, event):
		self.drag = 0
		self.mtt = None
		self.expose(widget,event)

	def on_motion_notify (self, widget, event):
		if self.drag:
			flag = 0
			if self.sel:
				r1o = self.sel[0]
				c1o = self.sel[1]
				r2o = self.sel[2]
				c2o = self.sel[3]
			else:
				r1o,c1o,r2o,c2o = 0,0,0,0
			rownum = int((event.y-self.tht-4)/self.tht)+self.offnum
			if event.y - self.tht - 4 < 0:
				rownum = self.curr
			if rownum > len(self.lines)-2:
				rownum = len(self.lines)-2
			if event.x > self.tdx*10:
				if event.x < self.tdx*(10+self.maxaddr*3): # hex
					colnum = int(((event.x-self.tdx*9.5)/self.tdx+1.5)/3)
				elif event.x < self.tdx*(11+self.maxaddr*4): #ascii
					colnum = int((event.x-self.tdx*(11+self.maxaddr*3))/self.tdx)+1
				else:
					colnum = self.line_size(rownum)
			else:
				colnum = self.curc
			if colnum > self.line_size(rownum):
				colnum = self.line_size(rownum)
			if colnum < 0:
				colnum = 0
			c2 = colnum
			c1 = self.curc
			if self.curr > rownum:
				r1 = rownum
				r2 = self.curr
				c1 = colnum
				c2 = self.curc+1
			else:
				r2 = rownum
				r1 = self.curr
			if r1 == r2 and c2 <= c1:
				c = c1
				c1 = c2
				c2 = c+1
			self.sel = r1,c1,r2,c2
			s = c2-c1
			if r1 != r2:
				s = self.lines[r2][0]+ c2 - self.lines[r1][0]-c1
			if s > 0:
				self.mtt = event.x,event.y,s
			else:
				self.mtt = None
			if c1 != c1o or c2 != c2o or r1 != r1o or r2 != r2o:
				self.expose(widget,event)
			self.parent.calc_status(self.data[self.lines[r1][0]+c1:self.lines[r2][0]+c2],s)

	def on_button_press (self, widget, event):
		rownum = int((event.y-self.tht-4)/self.tht)+self.offnum
		if event.y - self.tht - 4 < 0:
			rownum = self.curr
		if rownum > len(self.lines)-2:
			rownum = len(self.lines)-2
		if event.x > self.tdx*10:
			if event.x < self.tdx*(10+self.maxaddr*3): # hex
				colnum = int((event.x-self.tdx*9.5)/self.tdx/3)
			elif event.x < self.tdx*(11+self.maxaddr*4): #ascii
				colnum = int((event.x-self.tdx*(12+self.maxaddr*3))/self.tdx)
			else:
				colnum = self.line_size(rownum)-1
		else:
			colnum = self.curc
		if colnum > self.line_size(rownum)-1:
			colnum = self.line_size(rownum)-1
		if colnum < 0:
			colnum = self.curc
		self.prer = self.curr
		self.prec = self.curc
		self.curr = rownum
		self.curc = colnum
		self.sel = None
		self.drag = 1
		self.mode = "c"
		self.expose(widget,event)
		self.hv.grab_focus()

	def get_string(self, num):
		hex = ""
		asc = ""
		if self.hvlines[num] == "":
			ls = self.line_size(num)
			for j in range(ls):
				ch = self.data[self.lines[num][0]+j]
				hex += "%02x "%ord(ch)
				if ord(ch) < 32 or ord(ch) > 126:
					ch = unicode("\xC2\xB7","utf8")
				asc += ch
			self.hvlines[num] = (hex,asc)
		return self.hvlines[num]

	def expose (self, widget, event):
		ctx = self.hv.window.cairo_create()
		ctx.select_font_face("Monospace", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
		ctx.set_font_size(14)
		ctx.set_line_width(1)
		cmnt_off = (-1,-1)
		if self.tdx == -1:
			self.set_dxdy()
		x,y,width,height = self.hv.allocation
		self.numtl = min(int((height - self.tht-4)/self.tht)+1,len(self.lines))
		self.hbox2.set_size_request(max(width-self.tdx*(10+self.maxaddr*3),0),0)
		if self.numtl >= len(self.lines):
			self.vs.hide()
		else:
			self.vs.show()
		if width >= self.tdx*(9+self.maxaddr*3):
			self.hs.hide()
		else:
			self.hs.show()

		if self.mode == "":
			# clear top address lane
			ctx.rectangle(0,0,width,self.tht+4)
			ctx.set_source_rgb(0.9,0.9,0.9)
			ctx.fill()
			# clear everything else
			ctx.rectangle(0,self.tht+4,width,height)
			ctx.set_source_rgb(1,1,1)
			ctx.fill()
			# draw lines
			ctx.set_source_rgb(0,0,0)
			ctx.move_to(self.tdx*9+0.5,0)
			ctx.line_to(self.tdx*9+0.5,height)
			ctx.move_to(self.tdx*(10+self.maxaddr*3)+0.5,0)
			ctx.line_to(self.tdx*(10+self.maxaddr*3)+0.5,height)
			ctx.move_to(self.tdx*(12+self.maxaddr*4)+0.5,0)
			ctx.line_to(self.tdx*(12+self.maxaddr*4)+0.5,height)
			ctx.stroke()
			
			if self.sel and (self.sel[0] >= self.offnum and self.sel[0] <= self.offnum + self.numtl):
				if self.sel[0] == self.sel[2]: # one row
					ctx.rectangle(self.tdx*(10+self.sel[1]*3),self.tht*(self.sel[0]+1-self.offnum)+6.5,self.tdx*(self.sel[3]-self.sel[1])*3-self.tdx,self.tht)
					ctx.rectangle(self.tdx*(11+self.sel[1]+self.maxaddr*3),self.tht*(self.sel[0]+1-self.offnum)+6,self.tdx*(self.sel[3]-self.sel[1]),self.tht+1.5)
				else:
					# 1st sel row
					ctx.rectangle(self.tdx*(10+self.sel[1]*3),self.tht*(self.sel[0]+1-self.offnum)+6.5,self.tdx*(self.lines[self.sel[0]+1][0]-self.lines[self.sel[0]][0]-self.sel[1])*3-self.tdx,self.tht)
					ctx.rectangle(self.tdx*(11+self.sel[1]+self.maxaddr*3),self.tht*(self.sel[0]+1-self.offnum)+6,self.tdx*(self.lines[self.sel[0]+1][0]-self.lines[self.sel[0]][0]-self.sel[1]),self.tht+1.5)
					# middle rows
					for i in range(self.sel[2]-self.sel[0]-1):
						ctx.rectangle(self.tdx*10,self.tht*(self.sel[0]+i+2-self.offnum)+6.5,self.tdx*(self.lines[self.sel[0]+i+2][0]-self.lines[self.sel[0]+i+1][0])*3-self.tdx,self.tht)
						ctx.rectangle(self.tdx*(11+self.maxaddr*3),self.tht*(self.sel[0]+i+2-self.offnum)+6,self.tdx*(self.lines[self.sel[0]+i+2][0]-self.lines[self.sel[0]+i+1][0]),self.tht+1.5)
					# last sel row
					ctx.rectangle(self.tdx*10,self.tht*(self.sel[2]+1-self.offnum)+6.5,self.tdx*self.sel[3]*3-self.tdx,self.tht)
					ctx.rectangle(self.tdx*(11+self.maxaddr*3),self.tht*(self.sel[2]+1-self.offnum)+6,self.tdx*self.sel[3],self.tht+1.5)
				ctx.set_source_rgb(0.7,0.9,0.8)
				ctx.fill()
#hdr
			hdr = ""
			ctx.move_to(self.tdx*(10+self.curc*3),self.tht+1.5)
			ctx.line_to(self.tdx*(12+self.curc*3),self.tht+1.5)
			ctx.set_source_rgb(0,0,0.8)
			ctx.stroke()
			ctx.set_source_rgb(0,0,0)

			for i in range(self.maxaddr):
				hdr += "%02x "%i
			ctx.move_to(self.tdx*10,self.tht)
			ctx.show_text(hdr)
			ctx.set_source_rgb(0,0,0.8)
			haddr = "%02x"%(self.lines[self.curr][0]+self.curc)
			ctx.move_to(self.tdx*(11+self.maxaddr*3),self.tht)
			ctx.show_text(haddr)
			ctx.set_source_rgb(0,0,0)
#addr 
			for i in range(min(len(self.lines)-self.offnum-1,self.numtl)):
				ctx.move_to(0,(i+2)*self.tht+4)
				if i == self.curr-self.offnum:
					ctx.set_source_rgb(0,0,0.8)
				ctx.show_text("%08x"%(self.lines[i+self.offnum][0]))
				ctx.set_source_rgb(0,0,0)
# hex/asc  part
			for i in range(min(len(self.lines)-self.offnum-1,self.numtl)):
				ctx.set_source_rgb(0,0,0)
				hex,asc = self.get_string(i+self.offnum)
				if self.debug == 1:
					print "mode 0",i,len(self.lines)-self.offnum-1,self.numtl,asc

				ctx.move_to(self.tdx*10,(i+2)*self.tht+4)
				ctx.show_text(hex)
				ctx.move_to(self.tdx*(10+1+self.maxaddr*3),self.tht*(i+2)+4)
				ctx.show_text(asc)
				# draw break line
				if self.lines[i+self.offnum][1] == 1 or self.lines[i+self.offnum][1] == 3:
					ctx.move_to(self.tdx*10+0.5,(i+2)*self.tht+5.5)
					ctx.set_source_rgb(1,0,0.8)
					ctx.line_to(self.tdx*(10+self.maxaddr*3),self.tht*(i+2)+5.5)
					ctx.stroke()
				# show comment
				if self.lines[i+self.offnum][1] > 1:
					if len(self.lines[i+self.offnum]) > 2:
						if self.comments.has_key(self.lines[i+self.offnum][2]):
							ctx.move_to(self.tdx*(13+self.maxaddr*4),self.tht*(i+2)+4)
							ctx.set_source_rgb(0.9,0,0)
							ctx.show_text(self.comments[self.lines[i+self.offnum][2]][1])
					else:
						self.lines[i+self.offnum] = (self.lines[i+self.offnum][0],self.lines[i+self.offnum][0]-2)

		# clear prev hdr cursor
		ctx.set_source_rgb(0.9,0.9,0.9)
		ctx.move_to(self.tdx*(10+self.prec*3),self.tht+1.5)
		ctx.line_to(self.tdx*(12+self.prec*3),self.tht+1.5)
		ctx.stroke()
		# clear prev hdr address
		ctx.rectangle(self.tdx*(11+self.maxaddr*3),0,self.tdx*8,self.tht+1.5)
		ctx.fill()
		# draw new hdr cursor
		ctx.set_source_rgb(0,0,0.8)
		ctx.move_to(self.tdx*(10+self.curc*3),self.tht+1.5)
		ctx.line_to(self.tdx*(12+self.curc*3),self.tht+1.5)
		ctx.stroke()
		
		#draw haddr
		haddr = "%02x"%(self.lines[self.curr][0]+self.curc)
		ctx.move_to(self.tdx*(11+self.maxaddr*3),self.tht)
		ctx.show_text(haddr)

		#clear old and new hex and asc
		if self.debug == 1:
			print "mode c",self.prer,self.prec,self.curr,self.curc,self.offnum,self.maxaddr,self.lines[self.prer]
		if self.prer-self.offnum > -1:
			ctx.set_source_rgb(1,1,1)
			if self.sel:
				if self.sel[0] == self.sel[2]:
					if self.prer == self.sel[0] and self.prec >= self.sel[1] and self.prec < self.sel[3]:
						ctx.set_source_rgb(0.7,0.9,0.8)
				else:
					#1st row
					if self.prer == self.sel[0]:
						if self.prec >= self.sel[1] and self.prec <= self.lines[self.prer][0]:
							ctx.set_source_rgb(0.7,0.9,0.8)
					elif self.prer == self.sel[2]:
						if self.prec < self.sel[3]:
							ctx.set_source_rgb(0.7,0.9,0.8)
					elif self.prer > self.sel[0] and self.prer < self.sel[2]:
						ctx.set_source_rgb(0.7,0.9,0.8)
			if self.prec > -1 and self.prec < (self.lines[self.prer+1][0]-self.lines[self.prer][0]):
				# old hex char
				ctx.rectangle(self.tdx*(10+3*self.prec),(self.prer-self.offnum+1)*self.tht+6.5,self.tdx*2+1,self.tht)
				# old asc char
				ctx.rectangle(self.tdx*(11+self.prec+3*self.maxaddr),(self.prer-self.offnum+1)*self.tht+6,self.tdx+1,self.tht+1.5)
				ctx.fill()
			ctx.set_source_rgb(0,0,0)
			if self.prec > -1 and self.prec < (self.lines[self.prer+1][0]-self.lines[self.prer][0]):
				# location of hex
				ctx.move_to(self.tdx*(10+3*self.prec),(self.prer-self.offnum+2)*self.tht+4)
				ctx.show_text("%02x "%ord(self.data[self.lines[self.prer][0]+self.prec]))
				# location of asc
				ctx.move_to(self.tdx*(11+self.prec+3*self.maxaddr),(self.prer-self.offnum+2)*self.tht+4)
				ch = self.data[self.lines[self.prer][0]+self.prec]
				if ord(ch) < 32 or ord(ch) > 126:
					ch = unicode("\xC2\xB7","utf8")
				ctx.show_text(ch)

		if self.curr-self.offnum > -1:
			ctx.rectangle(self.tdx*(10+3*self.curc),(self.curr-self.offnum+1)*self.tht+6.5,self.tdx*2+1,self.tht)
			ctx.set_source_rgb(1,1,1)
			if self.sel:
				if self.sel[0] == self.sel[2]:
					if self.curr == self.sel[0] and self.curc >= self.sel[1] and self.curc < self.sel[3]:
						ctx.set_source_rgb(0.7,0.9,0.8)
				else:
					#1st row
					if self.curr == self.sel[0]:
						if self.curc >= self.sel[1] and self.curc <= self.lines[self.curr][0]:
							ctx.set_source_rgb(0.7,0.9,0.8)
					elif self.curr == self.sel[2]:
						if self.curc < self.sel[3]:
							ctx.set_source_rgb(0.7,0.9,0.8)
					elif self.curr > self.sel[0] and self.curr < self.sel[2]:
						ctx.set_source_rgb(0.7,0.9,0.8)
			ctx.fill()
			ctx.rectangle(self.tdx*(11+self.curc+3*self.maxaddr),(self.curr-self.offnum+1)*self.tht+6,self.tdx,self.tht+1)
			ctx.set_source_rgb(0.75,0.75,1)
			ctx.fill()
			ctx.set_source_rgb(0,0,1)
			ctx.move_to(self.tdx*(10+3*self.curc),(self.curr-self.offnum+2)*self.tht+4)
			ctx.select_font_face("Monospace", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
			ctx.show_text("%02x "%ord(self.data[self.lines[self.curr][0]+self.curc]))
			ctx.select_font_face("Monospace", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
			ctx.set_source_rgb(0,0,0)
			ctx.move_to(self.tdx*(11+self.curc+3*self.maxaddr),(self.curr-self.offnum+2)*self.tht+4)
			ch = self.data[self.lines[self.curr][0]+self.curc]
			if ord(ch) < 32 or ord(ch) > 126:
				ch = unicode("\xC2\xB7","utf8")
			ctx.show_text(ch)

		if self.prer != self.curr: # need to clear/draw addr
			if self.prer-self.offnum > -1:
				ctx.rectangle(0,(self.prer-self.offnum+1)*self.tht+4,self.tdx*8,self.tht)
				ctx.set_source_rgb(1,1,1)
				ctx.fill()
				ctx.set_source_rgb(0,0,0)
				ctx.move_to(0,(self.prer-self.offnum+2)*self.tht+4)
				ctx.show_text("%08x"%(self.lines[self.prer][0]))
			if self.curr-self.offnum > -1:
				ctx.rectangle(0,(self.curr-self.offnum+1)*self.tht+4,self.tdx*8,self.tht)
				ctx.set_source_rgb(1,1,1)
				ctx.fill()
				ctx.set_source_rgb(0,0,0.8)
				ctx.move_to(0,(self.curr-self.offnum+2)*self.tht+4)
				ctx.show_text("%08x"%(self.lines[self.curr][0]))
		# redraw break line
		if self.lines[self.curr][1] == 1 or self.lines[self.curr][1] == 3:
			ctx.move_to(self.tdx*10+0.5,(self.curr-self.offnum+2)*self.tht+5.5)
			ctx.set_source_rgb(1,0,0.8)
			ctx.line_to(self.tdx*(10+self.maxaddr*3),self.tht*(self.curr-self.offnum+2)+5.5)
			ctx.stroke()
		if self.lines[self.prer][1] == 1 or self.lines[self.prer][1] == 3:
			ctx.move_to(self.tdx*10+0.5,(self.prer-self.offnum+2)*self.tht+5.5)
			ctx.set_source_rgb(1,0,0.8)
			ctx.line_to(self.tdx*(10+self.maxaddr*3),self.tht*(self.prer-self.offnum+2)+5.5)
			ctx.stroke()

				
		if self.mtt:
			sh = 0
			if self.mtt[2] > 9999:
				sh = 4
			elif self.mtt[2] > 999:
				sh = 3
			elif self.mtt[2] > 99:
				sh = 2
			elif self.mtt[2] > 9:
				sh = 1

			ctx.rectangle(self.mtt[0]-self.tdx*0.5,self.mtt[1]-self.tht-6,self.tdx*(2+sh),self.tht+4) #-6
			ctx.set_source_rgba(0.9,0.95,0.95,0.85)
			ctx.fill()
			ctx.set_source_rgb(0.5,0,0)
			ctx.move_to(self.mtt[0],self.mtt[1]-6) #-6
			ctx.select_font_face("Monospace", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
			ctx.show_text("%d"%self.mtt[2])
			ctx.select_font_face("Monospace", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)

		ctx.select_font_face("Monospace", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
		for i in range(min(len(self.lines)-self.offnum-1,self.numtl)):
			if self.lines[i+self.offnum][1] > 1:
				if len(self.lines[i+self.offnum]) > 2:
					cmnt_off = self.lines[i+self.offnum][2]-self.lines[i+self.offnum][0]
					ctx.set_source_rgb(1,1,1)
					ctx.rectangle(self.tdx*(10+cmnt_off*3-1),self.tht*(i+1)+6,self.tdx,self.tht)
					ctx.fill()
					ctx.set_source_rgb(1,0,0.5)
					ctx.move_to(self.tdx*(10+cmnt_off*3-1),self.tht*(i+2)+4)
					ctx.show_text("[")
					clen = self.comments[self.lines[i+self.offnum][2]][0]
					r,c = self.get_sel_end(i+self.offnum,self.lines[i+self.offnum][2]+clen)
					if r <= min(len(self.lines)-self.offnum-1,self.numtl):
						ctx.set_source_rgb(1,1,1)
						ctx.rectangle(self.tdx*(10+c*3+2),self.tht*(r+1)+6,self.tdx,self.tht)
						ctx.fill()

						ctx.move_to(self.tdx*(10+c*3+2),self.tht*(r+2)+4)
						ctx.set_source_rgb(1,0,0.5)
						ctx.show_text("]")
					

		self.mode = ""

		return True