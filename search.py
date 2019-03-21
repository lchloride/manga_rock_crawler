import json
import sqlite3
import textwrap
import time
from appJar import gui
from PIL import Image, ImageTk
import os
import io
import requests as rs
import threading
import uuid
import math
import queue
import shutil
from datetime import datetime


class ImgDownloadThread(threading.Thread):
    def __init__(self, threadID, inQueue, outQueue, gui=None):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.name = 'IMG_DOWNLOAD_THREAD' + str(threadID)
        self.inQueue = inQueue
        self.outQueue = outQueue
        self.gui = gui
        self.stopFlag = False

    def run(self):
        # print("Starting " + self.name)
        with rs.Session() as s:
            while not self.stopFlag and not self.inQueue.empty():
                (url, filepath) = self.inQueue.get()
                data = self.downloadImageNew2(url, filepath, s)
                self.outQueue.put((url, data))

        # while self.stopFlag and not self.inQueue.empty():
        #     self.inQueue.get()

        print("Exiting " + self.name)

    def stop(self):
        # Note that if one thread received STOP sign, all undone tasks will be removed from jobQueue
        # Thus, this operation will stop other activated threads
        self.stopFlag = True

    def downloadImage(self, url, filepath=None, session=None):
        print('Fetch image...,', url, '->', filepath)
        if session is None:
            s = rs.Session()
        else:
            s = session
        r = s.get(url, stream=True, timeout=5)

        if filepath is None:
            filepath = url[url.rfind('/') + 1:]

        with open(filepath, "wb") as pdf:
            for chunk in r.iter_content(chunk_size=1024):

                # writing one chunk at a time to pdf file
                if chunk:
                    pdf.write(chunk)
        print('Done. Image at', filepath, '\n')

    def downloadImageNew(self, url, filepath=None, session=None):
        print('Fetch image...,', url, '->', filepath)
        if session is None:
            s = rs.Session()
        else:
            s = session
        if filepath is None:
            filepath = url.split('/')[-1]
        cnt = 0
        while cnt < 3:
            try:
                r = s.get(url, stream=True, timeout=5)
                with open(filepath, 'wb') as f:
                    shutil.copyfileobj(r.raw, f)
            except rs.exceptions.ReadTimeout as e:
                cnt += 1
            except Exception as e:
                cnt += 1
                time.sleep(1)
            else:
                break
        if cnt >= 3:
            print('SOMETHING WRONG')
        else:
            print('Done. Image at', filepath, '\n')

    def downloadImageNew2(self, url, filepath=None, session=None):
        print('Fetch image...,', url, '->', filepath)
        if session is None:
            s = rs.Session()
        else:
            s = session
        if filepath is None:
            filepath = url.split('/')[-1]
        cnt = 0
        r = None
        while cnt < 3:
            try:
                r = s.get(url, timeout=5)
            except rs.exceptions.ReadTimeout as e:
                cnt += 1
            except Exception as e:
                cnt += 1
                time.sleep(1)
            else:
                break
        if cnt >= 3:
            print('SOMETHING WRONG')
        else:
            print('Done. Image at', filepath, '\n')
        if r is not None:
            return r.content
        else:
            return None


class MangaSearcher:
    def __init__(self, parent=None, language="ENGLISH"):
        self.parent = parent
        self.conf = {'width': 950, 'height': 740,
                     'block_max_width': 140, 'block_max_height': 210,
                     'manga_bg': '#dbdbdb', 'result_width': 140, 'info_width': 270,
                     'blocks_per_page': 12, "chapters_per_page": 25
                     }
        self.app = gui("MangaRock Searcher", "%dx%d" % (self.conf['width'], self.conf['height']))
        self.tempPath = os.path.join(".", "temp")
        if not os.path.isdir(self.tempPath):
            os.mkdir(self.tempPath)
        self.conn = sqlite3.connect('data.db')
        self.page = 0
        self.searchInfo = None
        self.metaInfo = None
        self.authorInfo = None
        self.authorFlag = False
        self.searchFlag = False
        self.mangaMeta = None
        self.chapterStart = 0
        self.timeout = 5
        self.__setLayout()

    def __setLayout(self):
        app = self.app
        conf = self.conf

        app.setBg(conf['manga_bg'])
        app.setFg('black')

        # app.setSticky("W")
        # app.setStretch("COLUMN")

        # Set stop function
        def checkStop():
            self.conn.close()
            return True

        app.setStopFunction(checkStop)
        app.setStartFunction(self.startFunction)

        # Search bar
        app.addLabelEntry("Keywords", row=0, column=0, colspan=3)
        app.addButton("Search", func=self.onSearchClicked, row=0, column=3, colspan=1)
        app.addLabel('Result', "Started", row=0, column=4, colspan=2)
        app.addHorizontalSeparator(1, 0, 6, colour="gray")

        for row in range(2):
            for column in range(6):
                iid = str(row * 6 + column)
                app.startFrame("BLOCK_" + iid, row=row + 3, column=column)
                # app.setBg("#11"+str(row)+str(row)+str(column)+str(column))
                app.setSticky("NEW")
                app.setStretch("COLUMN")
                bg0 = Image.open("bg.png")
                bg = bg0.resize((self.conf['block_max_width'], self.conf['block_max_height']), Image.ANTIALIAS)
                bgg = ImageTk.PhotoImage(bg)
                app.addImageData("pic_" + iid, bgg, fmt="PhotoImage")
                app.addMessage('Title_' + iid, text="")
                app.setMessageWidth('Title_' + iid, conf['result_width'])
                app.addLabel('Author_' + iid, text="")
                app.setLabelWidth('Author_' + iid, conf['result_width'])
                app.addLabel('Info_' + iid, text="")
                app.setLabelWidth('Info_' + iid, conf['result_width'])
                app.setImageSubmitFunction("pic_" + iid, self.onImageClicked)
                app.stopFrame()

        app.addHorizontalSeparator(5, 0, 6, colour="gray")

        app.addLabelEntry('Page', column=0)
        app.addButtons(['JumpToPage', 'FirstPage', 'PrevPage', 'NextPage', 'LastPage'],
                       [self.onJumpToPageClicked, self.onFirstPageClicked, self.onPrevPageClicked,
                        self.onNextPageClicked, self.onLastPageClicked],
                       row=6, column=1, colspan=3)

        app.enableEnter(self.onSearchClicked)

        # Show Series Subwindow
        app.startSubWindow(name='Series', title="View Series", modal=True)
        app.setSize(720, 640)
        app.setSticky("NW")
        app.startFrame("LEFT", row=0, column=0, rowspan=1, colspan=1)

        app.setSticky("NW")
        app.setStretch("COLUMN")
        app.setBg('#eaeaea')

        app.startFrame('RR', row=0, column=1)
        app.setSticky("NW")
        app.setPadX(2)
        app.setFont(13)

        app.addLabel('InfoL', 'Information')
        app.getLabelWidget("InfoL").config(font=("Comic Sans", "14", "bold"))

        # Name list
        aliasList = ["N/A"]
        app.addLabel('NameL', 'Name:', row=1, column=0)
        aliasStr = ''
        for i, alias in enumerate(aliasList):
            aliasStr += alias + '\n'
        aliasStr = aliasStr[:-1]
        app.addMessage('NameMsg', aliasStr, row=1, column=1)
        app.setMessageWidth('NameMsg', conf['info_width'])
        rowCnt = 2

        # Author
        author = "N/A"
        app.addLabel('AuthorL', 'Author:', row=rowCnt, column=0)
        app.addMessage('AuthorMsg', author, row=rowCnt, column=1)
        app.setMessageWidth('AuthorMsg', conf['info_width'])
        rowCnt += 1

        # Chapter
        app.addLabel('ChapterL', 'Total chapter:', row=rowCnt, column=0)
        app.addMessage('ChapterMsg', 'N/A', row=rowCnt, column=1)
        app.setMessageWidth('ChapterMsg', conf['info_width'])
        rowCnt += 1

        # State
        app.addLabel('StateL', 'State:', row=rowCnt, column=0)
        app.addMessage('StateMsg', 'N/A', row=rowCnt, column=1)
        app.setMessageWidth('StateMsg', conf['info_width'])
        rowCnt += 1

        # Last updated
        # lastUpdated = 0
        # lastUpdatedStr = datetime.utcfromtimestamp(lastUpdated).strftime('%Y-%m-%d %H:%M:%S')
        app.addLabel('LastUpdatedL', 'Last Updated:', row=rowCnt, column=0)
        app.addMessage('LastUpdatedMsg', 'N/A', row=rowCnt, column=1)
        app.setMessageWidth('LastUpdatedMsg', conf['info_width'])
        rowCnt += 1

        # Label
        labelList = ['N/A']
        labelStr = ''
        for l in labelList:
            labelStr += app.translate(l, '--') + ', '
        labelStr = labelStr[:-2]
        app.addLabel('LabelL', 'Labels:', row=rowCnt, column=0)
        app.addMessage('LabelMsg', labelStr, row=rowCnt, column=1)
        app.setMessageWidth('LabelMsg', conf['info_width'])
        rowCnt += 1

        app.stopFrame()

        app.startFrame('RRB', row=1, column=1)
        app.setSticky("NW")
        app.setPadX(2)
        app.setFont(13)

        # Intro
        intro = "N/A"
        app.addLabel('IntroL', 'Introduction:', row=rowCnt, column=0)
        app.addMessage('IntroMsg', intro, row=rowCnt, column=1)
        # app.setMessageWidth('IntroMsg', conf['info_width']+5)
        rowCnt += 1
        app.addLink('More..', self.loadFullIntro, row=rowCnt, column=1)
        app.hideLink('More..')
        rowCnt += 1

        # Frame ends
        app.stopFrame()
        app.stopFrame()

        # Chpater list frame starts
        app.startFrame('RIGHT', row=0, column=1)

        app.setSticky("NW")
        app.setStretch('ROW')

        app.addLabel("ChapterList", "Chapter List")
        app.addLabelOptionBox("ChapterStarts", ["N/A"])
        app.setOptionBoxChangeFunction("ChapterStarts", self.changeChapterStarts)
        app.startFrame("RRBB")
        app.setSticky("NW")
        for i in range(self.conf['chapters_per_page']):
            app.addMessage("Chapter_" + str(i), "")
            app.setMessageWidth("Chapter_" + str(i), 340)
        app.stopFrame()
        app.stopFrame()

        app.stopSubWindow()

    def __defaultCallback(self, name):
        print(name)

    def loadFullIntro(self):
        self.app.infoBox('Introduction', self.mangaMeta['description'])

    def __postConnect(self, url, data, session=None):
        if session is None:
            s = rs.Session()
        else:
            s = session
        r = self.__post(url, data=data, session=s)
        if r is None:
            return "Cannot establish connnection"
        elif r.status_code >= 400:
            return "Failed to get response " + r.text
        obj = json.loads(r.text)
        if obj["code"] != 0:
            return str(obj["data"])
        else:
            return obj["data"]

    def onImageClicked(self, iid):
        idx = int(iid[iid.rfind('_') + 1:])
        seriesId = self.searchInfo[self.page * self.conf["blocks_per_page"] + idx]
        self.app.showSubWindow('Series')
        self.app.threadCallback(self.getSeriesInfo, self.loadSeries, seriesId)
        # Back to default
        self.updateNameMsg('N/A', ['N/A'])
        self.updateAuthorMsg('N/A')
        self.updateChapterMsg('N/A')
        self.updateStateMsg('N/A')
        labelList = ['N/A']
        self.updateLabelMsg(labelList)
        self.updateLastUpdatedMsg('N/A')
        self.updateIntroMsg('N/A')

        self.app.changeOptionBox('ChapterStarts', ['N/A'])
        for i in range(self.conf["chapters_per_page"]):
            self.app.setMessage("Chapter_" + str(i), "")

    def getSeriesInfo(self, seriesId):
        cnt = 0
        r = None
        while cnt < 3:
            try:
                r = rs.get('https://api.mangarockhd.com/query/web401/info?oid=%s&last=0&country=Japan'
                           % str(seriesId), timeout=self.timeout)
            except rs.exceptions.ReadTimeout as e:
                cnt += 1
            except Exception as e:
                cnt += 1
                time.sleep(1)
            else:
                break

        if r is None or cnt >= 3:
            return None
        # print(r.text)
        obj = json.loads(r.text)
        if obj['code'] != 0:
            return None
        else:
            obj['data']['mrs_series'] = str(seriesId)
            return obj['data']

    def loadSeries(self, metaObj):
        self.mangaMeta = metaObj
        self.updateNameMsg(metaObj['name'], metaObj['alias'])
        self.updateAuthorMsg(metaObj['author'])
        self.updateChapterMsg(metaObj['total_chapters'])
        self.updateStateMsg(metaObj['completed'])
        labelList = []
        for label in metaObj['rich_categories']:
            labelList.append(self.app.translate(label['name'], '--'))
        self.updateLabelMsg(labelList)
        self.updateLastUpdatedMsg(metaObj['last_update'])
        self.updateIntroMsg(metaObj['description'])

        newChapterStarts = list(range(1, len(metaObj['chapters']), self.conf["chapters_per_page"]))
        self.app.changeOptionBox('ChapterStarts', newChapterStarts)
        self.loadChapterList()

    def loadChapterList(self):
        self.chapterStart = int(self.app.getOptionBox('ChapterStarts'))
        # Load chapters from chapterStarts-1 to chapterStarts-1+self.conf["chapters_per_page"]
        for i in range(min(self.conf["chapters_per_page"],
                           len(self.mangaMeta['chapters']) - self.chapterStart)):
            idx = self.chapterStart - 1 + i
            name = self.mangaMeta['chapters'][idx]['name']
            if len(name) > 50:
                name = name[:47] + "..."
            self.app.setMessage("Chapter_" + str(i), name)

        for i in range(min(self.conf["chapters_per_page"],
                           len(self.mangaMeta['chapters']) - self.chapterStart), self.conf["chapters_per_page"]):
            self.app.setMessage("Chapter_" + str(i), "")

    def updateNameMsg(self, name, aliasList):
        aliasStr = name + '\n'
        for i, alias in enumerate(aliasList):
            if i > 5:
                break
            if alias != name:
                aliasStr += alias.strip() + ';\n'
        aliasStr = aliasStr[:-1]
        self.app.setMessage('NameMsg', aliasStr)

    def updateAuthorMsg(self, author):
        self.app.setMessage('AuthorMsg', author)

    def updateChapterMsg(self, totalChapter):
        self.app.setMessage('ChapterMsg', totalChapter)

    def updateStateMsg(self, isCompleted):
        self.app.setMessage('StateMsg',
                            self.app.translate('CompletedMsg', "Completed")
                            if isCompleted else self.app.translate('OngoingMsg', "Ongoing"))

    def updateLastUpdatedMsg(self, lastUpdated):
        if type(lastUpdated) == int:
            lastUpdatedStr = datetime.utcfromtimestamp(lastUpdated).strftime('%Y-%m-%d %H:%M:%S')
        else:
            lastUpdatedStr = lastUpdated
        self.app.setMessage('LastUpdatedMsg', lastUpdatedStr)

    def updateLabelMsg(self, labelList):
        labelStr = ''
        for l in labelList:
            labelStr += l + ', '
        labelStr = labelStr[:-2]
        self.app.setMessage('LabelMsg', labelStr)

    def updateIntroMsg(self, intro):
        lineCnt = 12
        # print(self.rrFrameHeight, lineCnt)
        w = 42
        t = self.textWrap(intro, width=w, lineCnt=lineCnt)
        if t.endswith('...'):
            t = self.textWrap(intro, width=w, lineCnt=lineCnt - 1)
            self.app.showLink('More..')
        else:
            self.app.hideLink('More..')
        self.app.setMessage('IntroMsg', t)

    def textWrap(self, text, width=70, lineCnt=None):
        s = ''
        i = 0
        for line in text.split('\n'):
            for t in textwrap.wrap(line, width=width):
                if lineCnt is not None and i >= lineCnt:
                    s = s[:-1] + '...\n'
                    break
                i += 1
                s += t + '\n'
            if len(line) > 0:
                i += 1
                s += '\n'
        return s.strip()

    def changeChapterStarts(self, ev):
        self.loadChapterList()

    def getSearchInfo(self, keywords, session=None):
        return self.__postConnect("https://api.mangarockhd.com/query/web401/mrs_search?country=Japan",
                                  data=json.dumps({"type": "series", "keywords": str(keywords)}), session=session)

    def getMeta(self, idList, session=None):
        self.authorInfo = self.__postConnect("https://api.mangarockhd.com/meta?country=Japan",
                                             data=json.dumps(idList), session=session)
        return self.authorInfo

    def getMetaThread(self, idList, session=None):
        self.app.threadCallback(self.getMeta, self.getMetaThreadCallback, idList, session)

    def getMetaThreadCallback(self, ev):
        metaInfo = self.metaInfo
        authorMeta = self.authorInfo
        for key in metaInfo:
            authorNameList = []
            for authorId in metaInfo[key]["author_ids"]:
                authorNameList.append(authorMeta[authorId]["name"])
            metaInfo[key]['author_names'] = authorNameList
        self.authorFlag = False
        print(metaInfo)

    def onSearchClicked(self, btn):
        if self.searchFlag:
            self.app.warningBox('MangaRock Searcher', 'A searching process is running')
            return

        self.searchFlag = True
        keywords = self.app.getEntry('Keywords')
        if len(keywords) == 0:
            self.app.warningBox('MangaRock Searcher', 'Please specify the keywords')
        self.app.setLabel("Result", "Searching...")
        self.app.thread(self.search, keywords)

    def search(self, keywords):
        self.page = 0
        self.searchInfo = None
        self.metaInfo = None
        self.authorInfo = None

        s = rs.Session()
        searchInfo = self.getSearchInfo(keywords, session=s)
        if type(searchInfo) == str:
            self.app.errorBox("MangaRock Searcher", searchInfo)
            return
        self.searchInfo = searchInfo
        self.prepareSearchMeta(s)

    def prepareSearchMeta(self, session=None):
        self.app.queueFunction(self.app.setLabel, "Result", "Loading results...")
        searchInfo = self.searchInfo[self.page * self.conf['blocks_per_page']:
                                     min(len(self.searchInfo), (self.page + 1) * self.conf['blocks_per_page'])]
        metaInfo = self.getMeta(searchInfo)
        self.metaInfo = metaInfo

        if type(searchInfo) == str:
            self.app.errorBox("MangaRock Searcher", metaInfo)
            return
        # Prepare author query
        authorList = []
        for key in metaInfo:
            authorList.extend(metaInfo[key]["author_ids"])

        # Prepare image query
        imgThreads = []
        imgQueue = queue.Queue()
        for i, key in enumerate(metaInfo):
            info = metaInfo[key]
            postfix = info['thumbnail'][info['thumbnail'].rfind('.'):]
            filename = str(uuid.uuid4()) + postfix
            imgQueue.put((info["thumbnail"],
                          os.path.join(".", "temp", filename),
                          ))
            info['filename'] = filename

        # Start img threads
        imgDataQueue = queue.Queue()
        for i in range(min(max(1, len(metaInfo) // 3), 6)):
            # for i in range(len(metaInfo)):
            imgThread = ImgDownloadThread(i, imgQueue, imgDataQueue)
            imgThreads.append(imgThread)
            imgThread.start()
            time.sleep(0.5)

        # Start author info thread
        self.authorFlag = True
        self.getMetaThread(authorList, session=session)

        for imgThread in imgThreads:
            imgThread.join()
        print("All tasks done.")

        imgData = {}
        while not imgDataQueue.empty():
            (url, data) = imgDataQueue.get()
            imgData[url] = data

        while self.authorFlag:
            time.sleep(1)

        self.displaySearch(imgData)

    def displaySearch(self, imgData):
        searchInfo = self.searchInfo[self.page * self.conf['blocks_per_page']:
                                     min(len(self.searchInfo), (self.page + 1) * self.conf['blocks_per_page'])]

        for i, key in enumerate(searchInfo):
            info = self.metaInfo[key]
            self.app.queueFunction(self.loadResultItem, info, i, imgData[info['thumbnail']])

        for i in range(len(self.metaInfo), 12):
            self.app.queueFunction(self.loadEmptyItem, i)

        self.app.setEntry('Page', self.page)
        if len(self.metaInfo) == 0:
            resultStr = 'No result found.'
        else:
            resultStr = "Found %d items, Page %d of %d" \
                        % (len(self.searchInfo), self.page + 1, math.ceil(len(self.searchInfo) / 12))
        self.app.setLabel('Result', resultStr)
        self.changePageButtonsState()
        self.searchFlag = False

    def loadResultItem(self, info, i, data):
        title = info['name']
        if len(title) > 50:
            title = title[:47] + "..."
        if data is None:
            img0 = Image.open(os.path.join('.', 'bg.png'))
            img = img0.resize((self.conf['block_max_width'], self.conf['block_max_height']), Image.ANTIALIAS)
            imgg = ImageTk.PhotoImage(img)
            self.app.queueFunction(self.app.setImageData, "pic_" + str(i), imgg, fmt="PhotoImage")
        else:
            try:
                # img0 = Image.open(os.path.join('.', 'temp', filename))
                img0 = Image.open(io.BytesIO(data))
                img = img0.resize((self.conf['block_max_width'], self.conf['block_max_height']), Image.ANTIALIAS)
                imgg = ImageTk.PhotoImage(img)
                self.app.queueFunction(self.app.setImageData, "pic_" + str(i), imgg, fmt="PhotoImage")
            except Exception as e:
                print('Cannot load image')
        self.app.queueFunction(self.app.setMessage, 'Title_' + str(i), text=title)
        authorStr = ""
        for name in info['author_names']:
            authorStr += name + ","
        authorStr = authorStr[:-1]
        self.app.queueFunction(self.app.setLabel, 'Author_' + str(i), text=authorStr)
        self.app.queueFunction(self.app.setLabel, 'Info_' + str(i),
                               text="Completed" if info['completed'] else "Ongoing")

    def loadEmptyItem(self, i):
        img0 = Image.open(os.path.join('.', 'bg.png'))
        img = img0.resize((self.conf['block_max_width'], self.conf['block_max_height']), Image.ANTIALIAS)
        imgg = ImageTk.PhotoImage(img)
        self.app.queueFunction(self.app.setImageData, "pic_" + str(i), imgg, fmt="PhotoImage")
        self.app.queueFunction(self.app.setMessage, 'Title_' + str(i), text='')
        self.app.queueFunction(self.app.setLabel, 'Author_' + str(i), text='')
        self.app.queueFunction(self.app.setLabel, 'Info_' + str(i), text='')

    def loadPageItems(self):
        if self.searchFlag:
            self.app.warningBox('MangaRock Searcher', 'A searching process is running')
            return

        self.searchFlag = True
        s = rs.Session()
        self.prepareSearchMeta(s)

    def changePageButtonsState(self):
        if self.page <= 0:
            self.app.setButtonState('PrevPage', 'disabled')
        else:
            self.app.setButtonState('PrevPage', 'active')

        if self.page >= math.ceil(len(self.searchInfo) / self.conf['blocks_per_page']) - 1:
            self.app.setButtonState('NextPage', 'disabled')
        else:
            self.app.setButtonState('NextPage', 'active')

    def onNextPageClicked(self):
        if self.page < math.ceil(len(self.searchInfo) / self.conf['blocks_per_page']) - 1:
            self.page += 1
            self.app.thread(self.loadPageItems)
        self.changePageButtonsState()

    def onPrevPageClicked(self):
        if self.page > 0:
            self.page -= 1
            self.app.thread(self.loadPageItems)
        self.changePageButtonsState()

    def onLastPageClicked(self):
        self.page = math.ceil(len(self.searchInfo) / self.conf['blocks_per_page']) - 1
        self.app.thread(self.loadPageItems)
        self.changePageButtonsState()

    def onFirstPageClicked(self):
        self.page = 0
        self.app.thread(self.loadPageItems)
        self.changePageButtonsState()

    def onJumpToPageClicked(self):
        page = self.app.getEntry("Page")
        if type(page) != int:
            self.app.errorBox("MangaRock Searcher", "Please type an integer!")
        elif 0 <= page - 1 <= math.ceil(len(self.searchInfo) / self.conf["blocks_per_page"]) - 1:
            self.page = page
            self.app.thread(self.loadPageItems)
            self.changePageButtonsState()
        else:
            self.app.errorBox("MangaRock Searcher", "Please type an integer in 1~%d"
                              % (math.ceil(len(self.searchInfo) / self.conf["blocks_per_page"]) - 1))

    def __createTempDB(self):
        sql = """﻿CREATE TABLE "tempfile" (
            "url"	TEXT NOT NULL,
            "filename"	TEXT NOT NULL,
            "create_time"	INTEGER NOT NULL,
            "last_modified_time"	INTEGER NOT NULL,
            "size"	INTEGER NOT NULL,
            "attrs"	TEXT NOT NULL DEFAULT '{}',
            PRIMARY KEY("url")
        );"""
        c = self.conn.cursor()
        # Create table
        c.execute(sql)
        self.conn.commit()

    def __post(self, url, data, tryTimes=3, session=None):
        cnt = 0
        if session is not None and type(session) == rs.Session:
            s = session
        else:
            s = rs.Session()
        r = None
        while cnt < tryTimes:
            try:
                r = s.post(url, data=data, timeout=self.timeout)
            except Exception as e:
                cnt += 1
                time.sleep(1)
            else:
                break
        if cnt >= tryTimes:
            return None
        else:
            return r

    def startFunction(self):
        pass


if __name__ == '__main__':
    ms = MangaSearcher()
    ms.app.go(language='English')
    # ms.app.go(language='English', startWindow='Series')
