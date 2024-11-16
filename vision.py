import av
import cv2
import numpy as np
import sounddevice as sd

container = av.open("VTS_02_1.VOB")

container.seek(int(0*1000000), whence='time', backward=True)

headerdata1 = np.array([0, 1, 0, 0, 0, 1, 1, 1, 1, 0, 1, 0])
headerdata2 = np.array([0, 1, 1, 1, 1, 0, 0, 0, 0, 1, 1, 0])

def split_padded(a,n):
    padding = (-len(a))%n
    return np.split(np.concatenate((a,np.zeros(padding, dtype=int))),n)

f = open('outfloat.floatpcm', 'wb')

outframe = np.zeros((520, 720), dtype=np.uint8)

outdata_active = np.zeros(40, dtype=np.uint8)
outdata_bytes = np.zeros(40, dtype=np.uint8)


starty = 695

class bytefilemaker():
	def __init__(self):
		self.counter = 0
		self.outbin = b''
		self.prevdata = b''
		self.startframe = -1
		self.hashlist = []

	def do_bytes(self, activebytes, inbytes, framenum, betw):

		nno = np.nonzero(activebytes)
		if len(nno[0]):
			maxval = np.amax(nno)
			clearbytes = maxval!=19
		else:
			clearbytes = True

		#print(str(int(not clearbytes)), inbytes.tobytes().hex(), end='')

		if clearbytes:
			if self.outbin:
				self.outbin += inbytes.tobytes()
				header = self.outbin[:3][::-1]
				rand = self.outbin[3:5]
				data = self.outbin[5:]
				dhash = data.__hash__()
				if dhash not in self.hashlist:
					#f = open('out/'+str(self.startframe)+'_'+str(betw)+'_'+str(self.counter)+'.bin', 'wb')
					#f.write(data)
					self.hashlist.append(dhash)
					#print('OUT', data.hex())
				#else:
				#	print('REP', data.hex())

				print('OUT', header.hex(), len(data))

				self.outbin = b''
				self.counter += 1
				self.startframe = -1
		else:
			if self.startframe == -1: self.startframe = framenum
			self.outbin += inbytes.tobytes()
		return clearbytes

bfm = bytefilemaker()

h = 0

for framenum, frame in enumerate(container.decode(video=0)):
	frame = frame.to_ndarray(format='gray8')
	outframe[0:480] = frame[0:480]

	if True:
		dataside1 = frame[0::2][0:720, starty:700][:, 1]
		dataside2 = frame[1::2][0:720, starty:700][:, 1]

		dataside2 = np.roll(dataside2, 1)

		dataside1_o = (dataside1>100).astype(bool).astype(np.uint8)
		dataside2_o = (dataside2>100).astype(bool).astype(np.uint8)

		dataside1_visual = dataside1.astype(np.uint8)
		dataside1_visual = np.repeat(dataside1_visual, 3, axis=0)
		outframe[480][:] = dataside1_visual
		outframe[480:500] = outframe[480]

		dataside2_visual = dataside2.astype(np.uint8)
		dataside2_visual = np.repeat(dataside2_visual, 3, axis=0)
		outframe[500][:] = dataside2_visual
		outframe[500:] = outframe[500]

		headercheck1 = all(headerdata1==dataside1_o[1:13])
		headercheck2 = all(headerdata2==dataside2_o[1:13])


		outdata_active[0:20] = dataside1_o[13:210:10]
		outdata_active[20:40] = dataside2_o[13:210:10]

		outdata_bytes[:] = 0

		if headercheck1 and headercheck2:
			for x in range(8):
				outdata_bytes[0:20] += dataside1_o[14+x:210+x:10] << x
				outdata_bytes[20:40] += dataside2_o[14+x:210+x:10] << x
		else:
			outdata_active[:] = 0

		#print('1',end=' > ')
		outd = bfm.do_bytes(outdata_active[0:20], outdata_bytes[0:20], framenum, 0)
		#print()

		#print('2',end=' > ')
		outd2 = bfm.do_bytes(outdata_active[20:40], outdata_bytes[20:40], framenum, 1)
		#print()

		n = not (outd and outd2)


	if True:
		vm_frame = (frame[0:470, 0:50]/256).astype(dtype=np.float32)[0::2]

		if (framenum%10)==0 if n else (framenum%100)==0:
			cv2.imshow('frame', outframe)
			cv2.waitKey(1)