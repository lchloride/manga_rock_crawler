import requests as rs
import json
import os
import threading
from multiprocessing import Queue
import time
import codecs
import math


class MRIThread(threading.Thread):
    def __init__(self, threadID, inQueue, outQueue, gui=None):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.name = 'MRI_THREAD' + str(threadID)
        self.inQueue = inQueue
        self.outQueue = outQueue
        self.gui = gui
        self.stopFlag = False

    def run(self):
        print("Starting " + self.name)
        with rs.Session() as s:
            while not self.stopFlag and not self.inQueue.empty():
                (mri, mriFile, webpFile, pngFile) = self.inQueue.get()
                if self.downloadMRI(s, mri, mriFile):
                    self.outQueue.put((mriFile, webpFile, pngFile))
                    if self.gui is not None:
                        self.gui.mriProgress.inc()
                else:
                    if self.gui is None:
                        print('Failed to get data of', mri)
                    else:
                        self.gui.setDPMsg(2, 'Failed to get data of' + str(mri))

        # while self.stopFlag and not self.inQueue.empty():
        #     self.inQueue.get()

        self.outQueue.put((None, None, None))
        print("Exiting " + self.name)

    def stop(self):
        # Note that if one thread received STOP sign, all undone tasks will be removed from jobQueue
        # Thus, this operation will stop other activated threads
        self.stopFlag = True

    def downloadMRI(self, session, url, filepath=None):
        print('Fetch MRI file...')
        cnt = 0
        r = None
        while cnt < 3:
            try:
                r = session.get(url, stream=True, timeout=20)
            except rs.Timeout as e:
                print('Timeout', e.errno)
                cnt += 1
                time.sleep(1)
            except rs.RequestException as e:
                print('Connection error:', e.errno)
                cnt += 1
                time.sleep(1)
            except Exception as e:
                print('Error:', e)
                cnt += 1
                time.sleep(1)
            else:
                break
        if cnt >= 3:
            print('Failed to get manga file')
            return False

        if filepath is None:
            filepath = url[url.rfind('/') + 1:]

        with open(filepath, "wb") as mri:
            cnt = 0
            while cnt < 3:
                try:
                    for chunk in r.iter_content(chunk_size=1024):
                        # writing one chunk at a time to mri file
                        if chunk:
                            mri.write(chunk)
                except Exception as e:
                    print('Get data error', e)
                    time.sleep(1)
                    cnt += 1
                else:
                    break
        print('Done. MRI file at', filepath, '\n')
        return True


class ParseMRIThread(threading.Thread):
    def __init__(self, threadID, inQueue, outQueue, tempFileQueue=None, gui=None):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.name = 'PARSE_MRI_THREAD' + str(threadID)
        self.inQueue = inQueue
        self.outQueue = outQueue
        self.tempFileQueue = tempFileQueue
        self.gui = gui
        self.magicNum = 0x65
        self.stopFlag = False

    def run(self):
        print("Starting " + self.name)
        doneCnt = 0
        while not self.stopFlag and doneCnt < 2:
            (mriFile, webpFile, pngFile) = self.inQueue.get()
            if mriFile is None and webpFile is None and pngFile is None:
                doneCnt += 1
                continue
            if self.mri2webp(mriFile, webpFile):
                self.outQueue.put((webpFile, pngFile))
                if self.gui is not None:
                    self.gui.webpProgress.inc()
            if self.tempFileQueue is not None:
                self.tempFileQueue.put(mriFile)

        # while self.stopFlag and not self.inQueue.empty():
        #     self.inQueue.get()

        self.outQueue.put((None, None))
        if self.tempFileQueue is not None:
            self.tempFileQueue.put(None)
        print("Exiting " + self.name)

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
        return True

    def stop(self):
        self.stopFlag = True


class PNGThread(threading.Thread):
    def __init__(self, threadID, inQueue, outQueue=None, tempFileQueue=None, gui=None):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.name = 'PNG_THREAD' + str(threadID)
        self.inQueue = inQueue
        self.outQueue = outQueue
        self.tempFileQueue = tempFileQueue
        self.gui = gui
        self.stopFlag = False

    def run(self):
        print("Starting " + self.name)
        doneCnt = 0
        while not self.stopFlag and doneCnt < 1:
            (webpFile, pngFile) = self.inQueue.get()
            if webpFile is None and pngFile is None:
                doneCnt += 1
                self.inQueue.put((None, None))
                break
            if self.webp2png(webpFile, pngFile):
                if self.outQueue is not None:
                    self.outQueue.put(pngFile)
                if self.gui is not None:
                    self.gui.pngProgress.inc()

            if self.tempFileQueue is not None:
                self.tempFileQueue.put(webpFile)

        # while self.stopFlag and not self.inQueue.empty():
        #     self.inQueue.get()

        if self.tempFileQueue is not None:
            self.tempFileQueue.put(None)
        print("Exiting " + self.name)

    def webp2png(self, webpFile, pngFile=None):
        print('WEBP image to png image...')
        try:
            from PIL import Image
        except ImportError as e:
            print('Pillow must be installed to convert webp to png')
            return False
        if pngFile is None:
            pngFile = webpFile.replace('.webp', '.png')
        try:
            im = Image.open(webpFile).convert("RGBA")
        except Exception as e:
            print('Failed to read image webp')
            return False
        im.save(pngFile, "png")
        print('Done. PNG image at', pngFile, '\n')
        return True

    def stop(self):
        self.stopFlag = True


class TempFileThread(threading.Thread):
    def __init__(self, threadID, tempFileQueue):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.name = 'TEMP_FILE_THREAD' + str(threadID)
        self.queue = tempFileQueue
        self.stopFlag = False

    def run(self):
        print("Starting " + self.name)
        doneCnt = 0
        while not self.stopFlag and doneCnt < 3:
            file = self.queue.get()
            if file is None:
                print(doneCnt)
                doneCnt += 1
                continue
            print('Removing', file)
            os.remove(file)
        print("Exiting " + self.name, self.queue.empty())

    def stop(self):
        self.stopFlag = True


class MangaName:
    def __init__(self):
        self.posFactor = lambda idx: math.log(idx, 3)+1
        self.negFactor = lambda idx: idx ** 0.5
        # self.posFactor = lambda idx: idx ** 0.5
        # self.negFactor = lambda idx: idx ** 0.5

    def checkKorean(self, name):
        for ch in name:
            code = ord(ch)
            if 0x1100 <= code <= 0x11ff or 0x3130 <= code <= 0x318f or 0xa960 <= code <= 0xa97f:
                return True
        return False

    def checkJPKana(self, name):
        for ch in name:
            code = ord(ch)
            if 0x3040 <= code <= 0x30ff or 0x31f0 <= code <= 0x31ff or 0x3190 <= code <= 0x319f:
                return True
        return False

    def checkPureHanzi(self, name):
        if self.checkJPKana(name) or self.checkKorean(name):
            return False
        for ch in name:
            code = ord(ch)
            if 0x4e00 <= code <= 0x9fff or 0x3400 <= code <= 0x4dbf or \
                0x20000 <= code <= 0x2a6df or 0x2b740 <= code <= 0x2ceaf or 0xf900 <= code <= 0xfaff or \
                0x2f800 <= code <= 0x2fa1f:
                return True
        return False

    def divideRomaji(self, pinyin):
        pinyinList = []
        path = []
        with codecs.open('kana.json', 'r', 'utf-8') as f:
            data0 = json.load(f, encoding='utf-8')
        data = list(data0.keys())
        word = pinyin.lower().split(' ')
        for w in word:
            pyList = []
            self.dividePinyinR(w, data, path, pyList)
            if len(pyList) == 0:
                pyList = [w]
            pinyinList.append(pyList)
        return pinyinList

    def divideRomajiOld(self, romaji):
        tangoList = []
        temp = ''
        vol = lambda x: x in ['a', 'i', 'u', 'e', 'o', 'ō', 'ā', 'ē', 'ū', 'ī']
        con = lambda x: ord('a') <= ord(x) <= ord('z') and x not in ['a', 'i', 'u', 'e', 'o']
        you = lambda x: x in ['k', 'n', 'h', 'm', 'r', 'g', 'j', 'b', 'p']
        romaji = romaji.lower()
        word = romaji.split(' ')
        for w in word:
            for ch in w:
                if not (ord('a') <= ord(ch) <= ord('z')):
                    continue
                # print(temp, (temp[-1] if len(temp) > 0 else ''), ch)
                if len(temp) == 0:
                    temp += ch
                elif vol(temp[-1]) or temp == 'n':
                    tangoList.append(temp)
                    temp = ch
                elif con(temp[-1]):
                    if temp in ['sh', 'ch'] and not vol(ch):
                        tangoList.append(temp[0])
                        temp = temp[1]
                    if temp == 'ts' and ch != 'u':
                        tangoList.append(temp[0])
                        temp = temp[1]
                    if you(temp[-1]) and ch == 'y':
                        temp += ch
                    elif temp[-1] == ch:
                        temp += ch
                    elif temp[-1] == 't' and ch == 's':
                        temp += ch
                    elif temp[-1] in ['s', 'c'] and ch == 'h':
                        temp += ch
                    elif vol(ch):
                        temp += ch
                    else:
                        tangoList.append(temp)
                        temp = ch
                else:
                    tangoList.append(temp)
                    temp = ch
            tangoList.append(temp)
            temp = ''
        return tangoList

    def matchPinyin(self, name):
        div = self.dividePinyin(name)
        s = ''
        for w in div:
            minLen = 1000
            minDiv = []
            for d in w:
                if len(d) < minLen:
                    minDiv = d
                    minLen = len(d)
            for yj in minDiv:
                s += yj + ' '
        # print(s)
        return self.matchPinyinYinJie(s)

    def matchPinyinYinJie(self, name):
        with codecs.open('pinyin1.json', 'r', 'utf-8') as f:
            data = json.load(f, encoding='utf-8')
        name = name.lower()
        word = name.strip().split(' ')
        score = 0
        idx = 1
        inc = True
        for w in word:
            # print(score, w, inc, idx)
            if w in data:
                if not inc:
                    idx = 1
                    inc = True
                score += (data[w]+0.5) * self.posFactor(idx)
                idx += 1
            else:
                if inc:
                    idx = 1
                    inc = False
                score -= self.negFactor(idx)
                idx += 1
        # print(score, len(word))
        return score / len(word)

    def dividePinyin(self, pinyin):
        pinyinList = []
        path = []
        with codecs.open('pinyin.json', 'r', 'utf-8') as f:
            data = json.load(f, encoding='utf-8')
        word = pinyin.lower().split(' ')
        for w in word:
            pyList = []
            self.dividePinyinR(w, data, path, pyList)
            if len(pyList) == 0:
                pyList = [w]
            pinyinList.append(pyList)
        return pinyinList

    def dividePinyinR(self, pinyin, data, path, result):
        if len(pinyin) == 0:
            result.append(list(path))
            return
        for py in data:
            if pinyin.startswith(py):
                # print(pinyin, py)
                path.append(py)
                pinyin1 = pinyin[len(py):]
                self.dividePinyinR(pinyin1, data, path, result)
                path.pop()


    def matchKana(self, romaji):
        with codecs.open('kana.json', 'r', 'utf-8') as f:
            data = json.load(f, encoding='utf-8')
        div = self.divideRomaji(romaji)
        s = ''
        for w in div:
            minLen = 1000
            minDiv = []
            for d in w:
                if len(d) < minLen:
                    minDiv = d
                    minLen = len(d)
            for yj in minDiv:
                s += yj + ' '
        rList = s.strip().split(' ')
        score = 0
        idx = 1
        inc = True
        for r in rList:
            if len(r) >= 2 and r[0] == r[1]:
                r = r[1:]
            # print(score, r, inc, idx)
            if r in data:
                if not inc:
                    idx = 1
                    inc = True
                score += (data[r]+0.5) * self.posFactor(idx)
                idx += 1
            else:
                if inc:
                    idx = 1
                    inc = False
                score -= self.negFactor(idx)
                idx += 1
        # print(score, len(rList))
        return score / len(rList)

    def checkJPCN(self, nameList):
        isJK = False
        isCN = False
        cnName = '--'
        jpName = '--'
        newNameList = []
        for name in nameList:
            newNameList += name.split(';')
        for name in newNameList:
            if self.checkPureHanzi(name):
                isCN = True
                cnName = name
            if self.checkJPKana(name):
                isJK = True
                jpName = name

        if isJK:
            return 'JP', jpName
        elif isCN:
            highestJP = 0
            highestCN = 0
            jpname = ''
            cnname = ''
            for name in nameList:
                jpscore = self.matchKana(name)
                cnscore = self.matchPinyin(name)
                if jpscore > 0.5 and jpscore > highestJP:
                    highestJP = jpscore
                    jpname = name
                if cnscore > 0.5 and cnscore > highestCN:
                    highestCN = cnscore
                    cnname = name

            if highestCN == 0 and highestJP == 0:
                s = '--'
                r = nameList[0]
            elif highestJP >= highestCN:
                s = 'JP'
                r = jpName
            else:
                s = 'CN'
                r = cnName
            # print(s, cnName, jpName, '|', cnname, highestCN, '|', jpname, highestJP)
            return s, r
        else:
            return '--', nameList[0]


class MangaRock:
    def __init__(self, writer=None):
        self.magicNum = 0x65
        self.writer = writer

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
            filepath = url[url.rfind('/') + 1:]

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
        mriListNoCredit = []
        for item in data:
            mriList.append(item['url'])
            mriListNoCredit.append(item['url']) if 'role' not in item or item['role'].lower() != 'credit' else None
        print('Done.', len(data), 'items obtained.\n')
        return mriList, mriListNoCredit

    def getComicByChapter(self, chapterId, folder='./', to_png=True, delete_tempfile=True):
        self.write('Get comic of chapter %s......' % chapterId)
        mriList, mriListNoCredit = self.getMRIListByChapter(chapterId)
        for i, mri in enumerate(mriList):
            self.write('----------\nProcess image %d / %d' % (i + 1, len(mriList)))
            mriFile = os.path.join(folder, 'ch%s_%d.mri' % (chapterId, i + 1))
            webpFile = os.path.join(folder, 'ch%s_%d.webp' % (chapterId, i + 1))
            pngFile = os.path.join(folder, 'ch%s_%d.png' % (chapterId, i + 1))
            self.downloadMRI(mri, mriFile)
            self.mri2webp(mriFile, webpFile)
            if to_png:
                self.webp2png(webpFile, pngFile)
            if delete_tempfile:
                self.write('Remove temporary files...')
                os.remove(mriFile)
                if to_png:
                    os.remove(webpFile)
        self.write('Get comic of chapter %s finished.' % chapterId)

    def getComicByChapterMultiThread(self, chapterId, folder='./', delete_tempfile=True):
        self.write('Get comic of chapter %s......' % chapterId)
        mriList, mriListNoCredit = self.getMRIListByChapter(chapterId)
        jobQueue = Queue()
        mriQueue = Queue()
        webpQueue = Queue()
        tempFileQueue = Queue()
        for i, mri in enumerate(mriList):
            self.write('----------\nProcess image %d / %d' % (i + 1, len(mriList)))
            mriFile = os.path.join(folder, 'ch%s_%d.mri' % (chapterId, i + 1))
            webpFile = os.path.join(folder, 'ch%s_%d.webp' % (chapterId, i + 1))
            pngFile = os.path.join(folder, 'ch%s_%d.png' % (chapterId, i + 1))
            jobQueue.put((mri, mriFile, webpFile, pngFile))
        mriThread = MRIThread(1, jobQueue, mriQueue)
        mriThread1 = MRIThread(2, jobQueue, mriQueue)
        parseMRIThread = ParseMRIThread(1, mriQueue, webpQueue, tempFileQueue=tempFileQueue)
        pngThread = PNGThread(1, webpQueue, tempFileQueue=tempFileQueue)
        pngThread1 = PNGThread(2, webpQueue, tempFileQueue=tempFileQueue)
        mriThread.start()
        time.sleep(1)
        mriThread1.start()
        parseMRIThread.start()
        pngThread.start()
        time.sleep(1)
        pngThread1.start()
        if delete_tempfile:
            tempFileThread = TempFileThread(1, tempFileQueue)
            tempFileThread.start()
        self.write('Get comic of chapter %s finished.' % chapterId)

    def getSeriesInfo(self, seriesId):
        cnt = 0
        r = None
        while cnt < 3:
            try:
                r = rs.get('https://api.mangarockhd.com/query/web401/info?oid=mrs-serie-%s&last=0&country=Japan'
                           % seriesId)
            except Exception as e:
                cnt += 1
                time.sleep(1)
            else:
                break

        if r is None or cnt >= 3:
            return None
        print(r.text)
        obj = json.loads(r.text)
        if obj['code'] != 0:
            return None
        else:
            obj['data']['mrs_series'] = str(seriesId)
            return obj['data']

    def getChapterInfo(self, seriesInfo, chapterId):
        for i, info in enumerate(seriesInfo['chapters']):
            if info['oid'] == 'mrs-chapter-' + str(chapterId):
                seriesInfo['current_chapter'] = str(chapterId)
                break

    def write(self, content):
        if self.writer is None:
            print(content)
        else:
            self.writer.writeDownloadMsg(content)


if __name__ == '__main__':
    mr = MangaRock()
    # mr.getComicByChapter('100399152', folder='./ch100399152')
    # mr.getComicByChapterMultiThread('61805', folder='./ドメスティックな彼女_10')
    # mriList = mr.getMRIListByChapter('100399152')

    # mr.downloadMRI('https://f01.mrcdn.info/file/mrfiles/j/1/a/e/tB.cLwx5xUK.mri') # mriList[2]
    # mr.mri2webp('./tB.cLwx5xUK.mri', './tB.cLwx5xUK.webp')
    # mr.webp2png('./tB.cLwx5xUK.webp')
    # print(mr.getSeriesInfo('61792'))

    mn = MangaName()
    with codecs.open('namelist.json', 'r', 'utf-8') as f:
        dataa = json.load(f, encoding='utf-8')

    # print(len(dataa))
    for key in dataa:
        print(mn.checkJPCN(dataa[key]))
    # print(mn.checkPureHanzi('おそ松さん'))
    nnn = 'Gakuen Raku'
    print(mn.divideRomaji(nnn))
    print(mn.dividePinyin(nnn))
    print(mn.matchKana(nnn))
    print(mn.matchPinyin(nnn))


