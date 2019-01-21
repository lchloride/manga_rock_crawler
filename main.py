import requests as rs
import json
import os


class MangaRock:
    def __init__(self):
        self.magicNum = 0x65

    def mri2webp(self, mriFile, webpFile=None):
        print('MRI file to webp image...')
        if webpFile is None:
            webpFile = mriFile.replace('.mri', '.webp')

        with open(mriFile, 'rb') as fin:
            content = fin.read()
        size = len(content) + 7
        print('MRI file size:', len(content))
        contentArray = bytearray(content)
        sizeHex = size.to_bytes(4, byteorder='little')
        newContentArray = bytearray.fromhex('5249 4646')
        newContentArray += bytearray(sizeHex)
        newContentArray += bytearray.fromhex('5745 4250 5650 38')

        for i in range(len(contentArray)):
            contentArray[i] ^= self.magicNum
        newContentArray += contentArray

        print('WEBP file size', len(newContentArray))
        with open(webpFile, 'wb') as fout:
            fout.write(newContentArray)
        print('Done. WEBP Image at', webpFile, '\n')

    def webp2png(self, webpFile, pngFile=None):
        print('WEBP image to png image...')
        try:
            from PIL import Image
        except ImportError as e:
            print('Pillow must be installed to convert webp to png')
            raise e
        if pngFile is None:
            pngFile = webpFile.replace('.webp', '.png')
        im = Image.open(webpFile).convert("RGBA")
        im.save(pngFile, "png")
        print('Done. PNG image at', pngFile, '\n')

    def downloadMRI(self, url, filepath=None):
        print('Fetch MRI file...')
        r = rs.get(url, stream=True)

        if filepath is None:
            filepath = url[url.rfind('/')+1:]

        with open(filepath, "wb") as pdf:
            for chunk in r.iter_content(chunk_size=1024):

                # writing one chunk at a time to pdf file
                if chunk:
                    pdf.write(chunk)
        print('Done. MRI file at', filepath, '\n')

    def getMRIListByChapter(self, chapterId):
        print('Get MRI List by chapter ID...')
        r = rs.get('https://api.mangarockhd.com/query/web401/pagesv2?oid=mrs-chapter-%s&country=Japan' % chapterId)
        data = json.loads(r.content)['data']
        mriList = []
        for item in data:
            mriList.append(item['url'])
        print('Done.', len(data), 'items obtained.\n')
        return mriList

    def getComicByChapter(self, chapterId, folder='./', to_png=True, delete_tempfile=True):
        print('Get comic of chapter %s......' % chapterId)
        mriList = self.getMRIListByChapter(chapterId)
        for i, mri in enumerate(mriList):
            print('----------\nProcess image %d / %d' % (i+1, len(mriList)))
            mriFile = os.path.join(folder, 'ch%s_%d.mri' % (chapterId, i+1))
            webpFile = os.path.join(folder, 'ch%s_%d.webp' % (chapterId, i+1))
            pngFile = os.path.join(folder, 'ch%s_%d.png' % (chapterId, i+1))
            self.downloadMRI(mri, mriFile)
            self.mri2webp(mriFile, webpFile)
            if to_png:
                self.webp2png(webpFile, pngFile)
            if delete_tempfile:
                print('Remove temporary files...')
                os.remove(mriFile)
                if to_png:
                    os.remove(webpFile)
        print('Get comic of chapter %s finished.' % chapterId)



if __name__ == '__main__':
    mr = MangaRock()
    mr.getComicByChapter('100399152', folder='./ch100399152')
    # mriList = mr.getMRIListByChapter('100399152')

    # mr.downloadMRI('https://f01.mrcdn.info/file/mrfiles/j/1/a/e/tB.cLwx5xUK.mri') # mriList[2]
    # mr.mri2webp('./tB.cLwx5xUK.mri', './tB.cLwx5xUK.webp')
    # mr.webp2png('./tB.cLwx5xUK.webp')