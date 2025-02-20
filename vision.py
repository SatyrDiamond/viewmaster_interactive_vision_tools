import av
import cv2
import numpy as np
import sounddevice as sd

headerdata1 = np.array([0, 1, 0, 0, 0, 1, 1, 1, 1, 0, 1, 0])
headerdata2 = np.array([0, 1, 1, 1, 1, 0, 0, 0, 0, 1, 1, 0])

starty = 695

headerfilt = np.frombuffer(b'\xF0\xFF\xFF', dtype=np.uint8)
headermask = np.frombuffer(b'\x0F\x00\x00', dtype=np.uint8)

class frameproc():
	def __init__(self):
		self.outdata_active = np.zeros(40, dtype=np.uint8)
		self.outdata_bytes = np.zeros(40, dtype=np.uint8)
		self.numbytes = 0
		self.bytesub = 2
		self.outframe = np.zeros((520, 720), dtype=np.uint8)

	def load_video(self):
		self.container = av.open("VTS_02_2.VOB")
		self.framegen = self.container.decode(video=0)

	def seek(self, seconds):
		self.container.seek(int(seconds*1000000), whence='time', backward=True)
		self.framegen = self.container.decode(video=0)

	def proc_frame(self):
		self.frame = self.framegen.__next__()

		self.frame = self.frame.to_ndarray(format='gray8')

		dataside1 = self.frame[0::2][0:720, starty:700][:, 1]
		dataside2 = self.frame[1::2][0:720, starty:700][:, 1]

		dataside2 = np.roll(dataside2, 1)

		dataside1_o = (dataside1>100).astype(bool).astype(np.uint8)
		dataside2_o = (dataside2>100).astype(bool).astype(np.uint8)

		headercheck1 = all(headerdata1==dataside1_o[1:13])
		headercheck2 = all(headerdata2==dataside2_o[1:13])

		self.outdata_active[0:20] = dataside1_o[13:210:10]
		self.outdata_active[20:40] = dataside2_o[13:210:10]

		self.numbytes = 0
		self.outdata_bytes[:] = 0
		if headercheck1 and headercheck2:
			for x in range(8):
				self.outdata_bytes[0:20] += dataside1_o[14+x:210+x:10] << x
				self.outdata_bytes[20:40] += dataside2_o[14+x:210+x:10] << x
		else:
			self.outdata_active[:] = 0

	def getbytes(self):
		return self.outdata_bytes.tobytes()[0:self.numbytes]

	def view_frame(self, waitsec):
		self.outframe[0:480] = self.frame[0:480]
		
		dataside1 = self.frame[0::2][0:720, starty:700][:, 1]
		dataside2 = self.frame[1::2][0:720, starty:700][:, 1]
		dataside2 = np.roll(dataside2, 1)

		dataside1_visual = dataside1.astype(np.uint8)
		dataside1_visual = np.repeat(dataside1_visual, 3, axis=0)
		self.outframe[480][:] = dataside1_visual
		self.outframe[480:500] = self.outframe[480]

		dataside2_visual = dataside2.astype(np.uint8)
		dataside2_visual = np.repeat(dataside2_visual, 3, axis=0)
		self.outframe[500][:] = dataside2_visual
		self.outframe[500:] = self.outframe[500]

		vm_frame = (self.frame[0:470, 0:50]/256).astype(dtype=np.float32)[0::2]
		cv2.imshow('frame', self.outframe)
		cv2.waitKey(waitsec)

	def iter(self):
		self.bytesub += 1
		if self.bytesub > 1:
			self.proc_frame()
			self.bytesub = 0
		if self.bytesub == 0:
			return self.outdata_bytes[0:20][0:np.count_nonzero(self.outdata_active[0:20])].tobytes()
		if self.bytesub == 1:
			return self.outdata_bytes[20:40][0:np.count_nonzero(self.outdata_active[20:40])].tobytes()


class bytestate():
	def __init__(self):
		self.curstart = np.zeros(3, dtype=np.uint8)
		self.curstart[0] = 0
		self.curstart[1] = 0
		self.curstart[2] = 0

	def set(self, bytesd):
		if len(bytesd)>2:
			bufd = np.frombuffer(bytesd[0:3], dtype=np.uint8)
			self.curstart[0] = bufd[0]&0xf0
			self.curstart[1] = bufd[1]
			self.curstart[2] = bufd[2]

	def comp(self, bytesd):
		if len(bytesd)>2:
			bufd = np.frombuffer(bytesd[0:3], dtype=np.uint8)
			cond_1 = self.curstart[0] == bufd[0]&0xf0
			cond_2 = self.curstart[1] == bufd[1]
			cond_3 = self.curstart[2] == bufd[2]
			if cond_1 and cond_2 and cond_3: return bufd[0]&0x0f
		return -1

printdata = True

class datareader():
	def __init__(self):
		self.active = True
		self.outdata = b''
		self.penddata = b''
		self.state = bytestate()
		self.full = False
		self.cotin = False
		self.num = -1

	def pop(self):
		if self.full:
			outd = self.outdata
			self.outdata = b''
			self.full = False
			return self.num, outd

	def proc_bytes(self, bytesd):
		if not bytesd and self.active:
			self.active = False
			self.num = -1
		elif bytesd and not self.active:
			if len(bytesd)>2:
				self.active = True
				self.state.set(bytesd)
				self.penddata = b''
				#if printdata: print(self.state.curstart)
		if self.active:
			n = self.state.comp(bytesd)
			if n != -1: numchanged = self.num != n
			else: numchanged = False
			self.num = n
			if numchanged: 
				self.outdata = self.penddata
				self.penddata = b''
				self.penddata += bytesd
				if printdata: print(self.num, end=' ')
				self.full = True
			else: 
				self.penddata += bytesd
				if printdata: print(' ', end=' ')
		if printdata: print(bytesd.hex())

frame_obj = frameproc()
frame_obj.load_video()
frame_obj.seek(500)

reader_obj = datareader()

framenum = 0
while True:
	bytesd = frame_obj.iter()
	reader_obj.proc_bytes(bytesd)
	frame_obj.view_frame(1)
	outdata = reader_obj.pop()
	if outdata is not None:
		num, outdata = outdata
		outhex = reader_obj.state.curstart.tobytes().hex()
		filename = 'out\\frame_data_%s_%s_%s.bin' % (str(framenum//2), outhex, str(reader_obj.num))
		f = open(filename, 'wb')
		f.write(outdata)
	framenum += 1

exit()

