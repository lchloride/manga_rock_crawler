import requests as rs


class MangaRock:
    def __init__(self):
        self.magicNum = 0x65

    def mri2webp(self, mriFile, webpFile):
        with open(mriFile, 'rb') as fin:
            content = fin.read()
        size = len(content) + 7
        print(len(content))
        contentArray = bytearray(content)
        sizeHex = size.to_bytes(4, byteorder='little')
        print(sizeHex)
        sizeHexStr = 'c6b1 0800'
        newContentArray = bytearray.fromhex('5249 4646') # + sizeHexStr + ' 5745 4250 5650 3820')
        newContentArray += bytearray(sizeHex)
        newContentArray += bytearray.fromhex('5745 4250 5650 38')

        for i in range(len(contentArray)):
            contentArray[i] ^= self.magicNum
        newContentArray += contentArray

        print(len(newContentArray))
        with open(webpFile, 'wb') as fout:
            fout.write(newContentArray)






if __name__ == '__main__':
    mr = MangaRock()
    mr.mri2webp('./tB.cLwx5xUK.mri', './1.webp')