import io
import shutil
from appJar import gui
from PIL import Image, ImageTk
from datetime import datetime
from main import *
from data import *
from multiprocessing import Queue
import textwrap
import queue
import uuid


class AtomicInt:
    def __init__(self, value):
        self.value = value
        self.lock = threading.Lock()

    def set(self, value):
        self.lock.acquire()
        self.value = value
        self.lock.release()

    def get(self):
        return self.value

    def add(self, number):
        self.lock.acquire()
        self.value += number
        v = self.value
        self.lock.release()
        return v

    def inc(self):
        return self.add(1)

    def dec(self):
        return self.add(-1)


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


class MangaViewer:
    def __init__(self, language="ENGLISH"):
        self.conf = {'width': 950, 'height': 740,
                     'manga_max_width': 560, 'manga_max_height': 660,
                     'block_max_width': 140, 'block_max_height': 210, 'result_width': 140,
                     'manga_bg': 'black', 'info_width': 225, 'series_info_width': 270,
                     'blocks_per_page': 12, "chapters_per_page": 25
                     }
        self.app = gui("MangaRock Viewer", "%dx%d" % (self.conf['width'], self.conf['height']))
        self.mangaPath = './'
        self.nameMsgTitle = []
        self.mangaMeta = None
        self.currPage = -1  # starting from 0
        self.downloadParam = {}
        self.mangaList = []
        self.leftOffset = 0
        self.upOffset = 0
        self.zoomLevel = 0
        self.zoomSizeX = 20
        self.zoomSizeY = 20
        self.isDownloading = False
        self.isMetaReloading = False
        self.language = language
        self.langObj = None
        self.settingObj = None
        self.mriProgress = AtomicInt(0)
        self.webpProgress = AtomicInt(0)
        self.pngProgress = AtomicInt(0)
        self.threads = []
        self.downloadMangaURL = None
        self.rrFrameHeight = 0

        self.page = 0
        self.searchInfo = None
        self.metaInfo = None
        self.authorInfo = None
        self.authorFlag = False
        self.searchFlag = False
        self.seriesMeta = None
        self.chapterStart = 0
        self.timeout = 5

        self.readSettings()
        self.initLang()
        self.__setLayout()

    def initLang(self):
        with codecs.open('./lang.json', 'r', 'utf8') as f:
            self.langObj = json.load(f)
        if self.settingObj is not None and 'lang' in self.settingObj:
            self.language = self.getSetting('lang')

    def readSettings(self):
        with codecs.open('./settings.json', 'r', 'utf-8') as f:
            self.settingObj = json.load(f)

    def getSetting(self, key):
        if key not in self.settingObj:
            return None
        else:
            return self.settingObj[key]

    def putSetting(self, key, value):
        self.settingObj[key] = value

    def writeSettings(self):
        with codecs.open('./settings.json', 'w', 'utf-8') as f:
            json.dump(self.settingObj, f)

    def translate(self, key, default=None):
        if self.langObj is None or type(self.langObj) != dict:
            return default
        else:
            if self.language in self.langObj:
                if key in self.langObj[self.language]:
                    return self.langObj[self.language][key]
                else:
                    return default
            else:
                return default

    def changeLanguage(self, language):
        if language not in self.langObj:
            raise TypeError('Cannot find language info: ' + str(language))
        if self.mangaMeta is not None:
            self.app.setStatusbar('%s %d / %d' %
                                  (self.app.translate("ChapterSB", default="Chapter: "),
                                   self.mangaMeta['current_chapter'], self.mangaMeta['total_chapters']), 0)
            self.app.setStatusbar('%s %d / %d' % (self.app.translate("PageSB", "Page: "), self.currPage + 1,
                                                  len(self.mangaList)), 1)
            try:
                updatedAt = self.mangaMeta['chapters'][self.mangaMeta['current_chapter'] - 1]['updatedAt']
                updatedAtStr = datetime.utcfromtimestamp(updatedAt).strftime('%Y-%m-%d %H:%M:%S')
            except KeyError as e:
                updatedAtStr = 'N/A'
            self.app.setStatusbar('%s %s' % (self.app.translate("Updated atSB", "Updated at: "),
                                             updatedAtStr), 2)
            self.app.setStatusbar(self.app.translate("Zoom levelSB", "Zoom level: ") + ' ' +
                                  str(self.zoomLevel), 3)
            self.app.setStatusbar("%s %d, %s %d" % (self.app.translate("Position LeftSB", "Position Left: "),
                                                    self.leftOffset, self.app.translate("UpSB", " Up: "),
                                                    self.upOffset), 4)
        else:
            self.app.setStatusbar('%s N/A' %
                                  self.app.translate("ChapterSB", default="Chapter: "), 0)
            self.app.setStatusbar('%s N/A' % self.app.translate("PageSB", "Page: "), 1)

            updatedAtStr = 'N/A'
            self.app.setStatusbar('%s %s' % (self.app.translate("Updated atSB", "Updated at: "),
                                             updatedAtStr), 2)
            self.app.setStatusbar(self.app.translate("Zoom levelSB", "Zoom level: ") + ' N/A', 3)
            self.app.setStatusbar("%s N/A, %s N/A" % (self.app.translate("Position LeftSB", "Position Left: "),
                                                      self.app.translate("UpSB", " Up: ")), 4)

    def readImage(self, filepath):
        conf = self.conf
        oriImg0 = Image.open(filepath)
        if int(self.zoomLevel * self.zoomSizeX - self.leftOffset) < 0:
            self.leftOffset -= 50
        if int(self.zoomLevel * self.zoomSizeY - self.upOffset) < 0:
            self.upOffset -= 50
        if int(oriImg0.size[0] - self.leftOffset - self.zoomLevel * self.zoomSizeX) > oriImg0.size[0]:
            self.leftOffset += 50
        if int(oriImg0.size[1] - self.upOffset - self.zoomLevel * self.zoomSizeY) > oriImg0.size[1]:
            self.upOffset += 50

        box = (max(0, int(self.zoomLevel * self.zoomSizeX - self.leftOffset)),
               max(0, int(self.zoomLevel * self.zoomSizeY - self.upOffset)),
               min(oriImg0.size[0], int(oriImg0.size[0] - self.leftOffset - self.zoomLevel * self.zoomSizeX)),
               min(oriImg0.size[1], int(oriImg0.size[1] - self.upOffset - self.zoomLevel * self.zoomSizeY)))
        oriImg = oriImg0.crop(box)
        ratio = conf['manga_max_height'] / oriImg0.size[1] if oriImg0.size[1] > oriImg0.size[0] else \
            conf['manga_max_width'] / oriImg0.size[0]
        # ratio = 1 if oriImg.size[0] < conf['manga_max_width'] and \
        #              oriImg.size[1] < conf['manga_max_height'] else ratio
        newSize = (int(oriImg0.size[0] * ratio), int(oriImg0.size[1] * ratio))
        image0 = oriImg.resize(newSize, Image.ANTIALIAS)
        self.zoomSizeX = 20 if oriImg0.size[0] < 20 else (oriImg0.size[0] - 100) / 20
        self.zoomSizeY = 20 if oriImg0.size[1] < 20 else (oriImg0.size[1] - 100) / 20
        # print(box, ratio, newSize, self.zoomSizeX, self.zoomSizeY)
        img = ImageTk.PhotoImage(image0)
        return img

    def __setLayout(self):
        app = self.app
        conf = self.conf

        app.setBg(conf['manga_bg'])
        app.setFg('lightgray')

        tools = ["DOWNLOAD", "OPEN", "SEARCH", "REFRESH", "MD-fast-backward-alt", "MD-fast-forward-alt",
                 "MD-PREVIOUS", "MD-NEXT", "MD-REPEAT",
                 "ZOOM-IN", "ZOOM-OUT",
                 "ARROW-1-LEFT", "ARROW-1-RIGHT", "ARROW-1-UP",
                 "ARROW-1-DOWN", "SETTINGS", "HELP", "ABOUT", "OFF"]
        funcs = [self.openDownloadWindow, self.onOpenToolPressed, self.onSearchPressed,
                 self.onReloadMetaPressed,
                 self.loadPrevChapter, self.loadNextChapter,
                 self.loadPreviousManga, self.loadNextManga, self.jumpMangaPage,
                 self.onZoomInBtnPressed, self.onZoomOutBtnPressed, self.onMoveLeftBtnPressed,
                 self.onMoveRightBtnPressed, self.onMoveUpBtnPressed, self.onMoveDownBtnPressed,
                 self.openSettingWindow, self.openHelpWindow, self.openAboutWindow,
                 self.app.stop]

        app.addToolbar(tools, funcs, findIcon=True)

        # app.setToolbarButtonDisabled("OPEN")
        # app.setToolbarButtonDisabled("DOWNLOAD")
        # app.setToolbarButtonDisabled("REFRESH")
        app.setToolbarButtonDisabled("MD-fast-backward-alt")
        app.setToolbarButtonDisabled("MD-fast-forward-alt")
        app.setToolbarButtonDisabled("MD-PREVIOUS")
        app.setToolbarButtonDisabled("MD-NEXT")
        app.setToolbarButtonDisabled("MD-REPEAT")
        app.setToolbarButtonDisabled("ZOOM-IN")
        app.setToolbarButtonDisabled("ZOOM-OUT")
        app.setToolbarButtonDisabled("ARROW-1-LEFT")
        app.setToolbarButtonDisabled("ARROW-1-RIGHT")
        app.setToolbarButtonDisabled("ARROW-1-UP")
        app.setToolbarButtonDisabled("ARROW-1-DOWN")
        # app.setToolbarButtonDisabled("SETTINGS")
        # app.setToolbarButtonDisabled("HELP")
        # app.setToolbarButtonDisabled("ABOUT")
        app.setToolbarPinned(pinned=False)

        app.startFrame("LEFT", row=0, column=0, rowspan=1, colspan=2)
        app.setBg(conf['manga_bg'])
        app.setSticky("NEWS")
        app.setStretch("BOTH")

        app.addImageData('Manga', self.readImage('./intro.png'), fmt='PhotoImage')
        app.setImageSize('Manga', conf['manga_max_width'], conf['manga_max_height'])
        app.stopFrame()

        app.getImageWidget('Manga').bind('<Configure>', self.onImageSizeChanged)

        app.startFrame("RIGHT", row=0, column=2, rowspan=1, colspan=1)

        app.setSticky("NW")
        app.setStretch("COLUMN")
        app.setBg('#222222')
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
        # app.getFrameWidget('RR').bind('<Configure>', self.modifyIntroHeight)

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

        # State Bar
        # currPage = 0
        # updatedAt = 0
        # updatedAtStr = datetime.utcfromtimestamp(updatedAt).strftime('%Y-%m-%d %H:%M:%S')
        app.addStatusbar(fields=6)
        app.setStatusbar(self.translate("ChapterSB", default="Chapter: ") + "N/A", 0)
        app.setStatusbar(self.translate("PageSB", "Page: ") + "N/A", 1)
        app.setStatusbar(self.translate("Updated atSB", "Updated at: ") + "N/A", 2)
        app.setStatusbar(self.translate("Zoom levelSB", "Zoom level: ") + "N/A", 3)
        app.setStatusbar(self.translate("Position LeftSB", "Position Left: ") + "N/A" +
                         self.translate("UpSB", " Up: ") + "N/A", 4)
        app.setStatusbar("", 5)
        app.setStatusbarWidth(3, 0)
        app.setStatusbarWidth(3, 1)
        app.setStatusbarWidth(3, 3)
        app.setStatusbarWidth(15, 2)
        app.setStatusbarWidth(20, 5)

        # Help dialog
        app.startSubWindow("Help", modal=True)
        app.setFg('black')
        app.setSize(480, 620)
        app.setSticky('NW')
        app.setPadX(10)
        app.addIcon('Download manga chapter from MangaRock website', 'DOWNLOAD', compound='left')
        app.addIcon('Open manga local directory.', 'OPEN', compound='left')
        app.addIcon('Update information', 'REFRESH', compound='left')
        app.addIcon('Jump to previous page', 'MD-PREVIOUS', compound='left')
        app.addIcon('Jump to next page', 'MD-NEXT', compound='left')
        app.addIcon('Jump to specific page', 'MD-REPEAT', compound='left')
        app.addIcon('Zoom in manga picture', 'ZOOM-IN', compound='left')
        app.addIcon('Zoom out manga picture', 'ZOOM-OUT', compound='left')
        app.addIcon('Move left manga picture', 'ARROW-1-LEFT', compound='left')
        app.addIcon('Move right manga picture', 'ARROW-1-RIGHT', compound='left')
        app.addIcon('Move up manga picture', 'ARROW-1-UP', compound='left')
        app.addIcon('Move down manga picture', 'ARROW-1-down', compound='left')
        app.addIcon('Settings', 'SETTINGS', compound='left')
        app.addIcon('Help', 'HELP', compound='left')
        app.addIcon('About', 'ABOUT', compound='left')
        app.addIcon('Close application', 'OFF', compound='left')
        # set the button's name to match the SubWindow's name
        app.addNamedButton("Close", "Help", app.hideSubWindow)
        app.stopSubWindow()

        # ABOUT dialog
        app.startSubWindow("About", modal=True)
        app.setFg('black')
        app.setSize(480, 200)
        app.setSticky('NW')
        app.setFont(14)
        app.setPadX(10)

        app.addLabel('AboutTitleMsg', 'MangaRock Viewer')
        app.getLabelWidget("AboutTitleMsg").config(font=("Comic Sans", "16", "bold"))
        app.addMessage('AboutContentMsg', 'Created by lchloride, under MIT license.\n'
                                          'GitHub: https://github.com/lchloride/manga_rock_crawler.\n'
                                          'Issues and any ideas about this application are welcomed.')
        app.addWebLink('GitHub Repository Link', 'https://github.com/lchloride/manga_rock_crawler')
        # app.addWebLink('GitHub Repository Link', 'https://github.com/lchloride/manga_rock_crawler')
        app.setMessageWidth('AboutContentMsg', 450)

        # set the button's name to match the SubWindow's name
        app.addNamedButton("Close", "About", app.hideSubWindow)
        app.stopSubWindow()

        # DownloadProgress dialog
        app.startSubWindow("DownloadProgress", modal=True)
        app.setFg('black')
        app.setSize(480, 250)
        app.setSticky('W')
        app.setFont(14)
        app.setPadX(10)
        app.setPadY(5)

        app.addMessage('DPDownloadMsg0', 'Start downloading...')
        app.setMessageWidth('DPDownloadMsg0', 640)
        app.addMessage('DPDownloadMsg1', 'Preprocessing...')
        app.setMessageWidth('DPDownloadMsg1', 640)
        app.addMessage('DPDownloadMsg2', 'Meta data: --')
        app.setMessageWidth('DPDownloadMsg2', 640)
        app.addMessage('DPDownloadMsg3', '')
        app.setMessageWidth('DPDownloadMsg3', 640)
        app.addMessage('DPDownloadMsg4', '')
        app.setMessageWidth('DPDownloadMsg4', 640)
        app.addMessage('DPDownloadMsg5', '')
        app.setMessageWidth('DPDownloadMsg5', 640)

        # set the button's name to match the SubWindow's name
        app.addNamedButton("Force Quit", "DPBtn", self.onDPBtnPressed, row=7, column=0)
        app.stopSubWindow()

        # Download dialog
        app.startSubWindow("Download", modal=True)
        app.setFg('black')
        app.setSize(480, 200)
        app.setSticky('NW')
        app.setFont(14)
        app.setPadX(10)
        app.setPadY(10)

        app.addLabel("MangaURLL", "Manga URL")
        app.addEntry("MangaURLEntry", row=0, column=1)
        app.addNamedCheckBox('Use auto-download directory', 'AutoDownloadCB', colspan=2)
        app.addLabel('DirectoryL', 'Directory')
        app.addDirectoryEntry("DirectoryEntry", row=2, column=1)

        app.setCheckBoxChangeFunction('AutoDownloadCB', self.onAutoDownloadDirChanged)
        app.setLabelWidth('MangaURLL', 9)
        app.setLabelWidth('DirectoryL', 9)
        app.setEntryWidth('MangaURLEntry', 40)
        app.setEntryWidth('DirectoryEntry', 30)
        app.setFocus("MangaURLEntry")

        # set the button's name to match the SubWindow's name
        app.addNamedButton("Cancel", "DownloadCancel", self.onDownloadCancelPressed, 4, 0, 1)
        app.addNamedButton("OK", "DownloadOk", self.onDownloadOkPressed, 4, 1, 1)
        app.setButtonWidth('DownloadCancel', 6)
        app.setButtonWidth('DownloadOk', 6)
        app.stopSubWindow()

        # ======================
        # Setting dialog
        app.startSubWindow("Setting", modal=True)
        app.setFg('black')
        app.setSize(480, 450)
        app.setSticky('NW')
        app.setFont(14)
        app.setPadX(10)
        app.setPadY(10)

        app.startLabelFrame("LanguageLF", name='Language')
        app.addRadioButton("lang", "ENGLISH")
        app.addRadioButton("lang", "简体中文")
        app.stopLabelFrame()

        app.startLabelFrame("AutoLF", name='Auto Downloading')
        app.addNamedCheckBox("Enable auto downloading", "AutoCheckBox")
        app.addLabel('DirectoryL2', row=1, column=0)
        app.addDirectoryEntry('AutoDownloadDir', row=1, column=1)
        app.addLabel('NamingFormatL', row=2, column=0)
        app.addEntry('NamingEntry', row=2, column=1)
        app.setEntryWidth('NamingEntry', 30)
        app.addLabel('DirLabelsL', row=3, column=0)
        app.addButtons([['%MangaName%', '%JPMangaName%'],
                        ['%Order%', '%DateTime%'],
                        ['%ChapterTitle%']], self.onLabelBtnPressed, 3, 1)
        app.setButtonOverFunction('%MangaName%', self.displayLabelExample)
        app.setButtonOverFunction('%JPMangaName%', self.displayLabelExample)
        app.setButtonOverFunction('%Order%', self.displayLabelExample)
        app.setButtonOverFunction('%ChapterTitle%', self.displayLabelExample)
        app.setButtonOverFunction('%DateTime%', self.displayLabelExample)
        app.addLabel('LabelExampleL', '', row=4, colspan=2)
        app.addMessage('AutoDownloadIntro', row=5, colspan=2)
        app.setMessageWidth('AutoDownloadIntro', 450)
        app.stopLabelFrame()

        app.startLabelFrame('IgnoreCreditLF', name='Reading')
        app.addNamedCheckBox('Ignore credit page', 'IgnoreCreditCB')
        app.stopLabelFrame()

        # set the button's name to match the SubWindow's name
        app.addButtons(["Update", "Cancel"],
                       [self.onSettingUpdateBtnPressed, self.onSettingCancelPressed], 3, 0, 2)
        # app.addNamedButton("Cancel", "SettingCancel", app.hideSubWindow, row=2, column=0)
        # app.addNamedButton("OK", "SettingOk", self.onDownloadOkPressed, row=2, column=1)
        app.stopSubWindow()

        # ===================
        # Search Subwindow
        app.startSubWindow(name='Search', title="MangaRock Searcher", modal=True)
        app.setSticky('news')
        app.setStretch('COLUMN')
        app.setPadding([5,2])

        app.setSize(self.conf['width'], self.conf['height'])
        app.setBg('#dbdbdb')
        app.setFg('black')

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
                app.setMessageWidth('Title_' + iid, self.conf['result_width'])
                app.addLabel('Author_' + iid, text="")
                app.setLabelWidth('Author_' + iid, self.conf['result_width'])
                app.addLabel('Info_' + iid, text="")
                app.setLabelWidth('Info_' + iid, self.conf['result_width'])
                app.setImageSubmitFunction("pic_" + iid, self.onImageClicked)
                app.stopFrame()

        app.addHorizontalSeparator(5, 0, 6, colour="gray")

        app.addLabelEntry('Page', column=0)
        app.addButtons(['JumpToPage', 'FirstPage', 'PrevPage', 'NextPage', 'LastPage'],
                       [self.onJumpToPageClicked, self.onFirstPageClicked, self.onPrevPageClicked,
                        self.onNextPageClicked, self.onLastPageClicked],
                       row=6, column=1, colspan=3)

        app.enableEnter(self.onSearchClicked)
        app.stopSubWindow()
        # =======================

        # =======================
        # Series Subwindow
        app.startSubWindow(name='Series', title="View Series", modal=True)
        app.setSize(720, 640)
        app.setSticky("NW")
        app.startFrame("SERIES_LEFT", row=0, column=0, rowspan=1, colspan=1)

        app.setSticky("NW")
        app.setStretch("COLUMN")
        app.setBg('#dbdbdb')
        app.setFg('black')

        app.startFrame('SERIES_LL', row=0, column=1)
        app.setSticky("NW")
        app.setPadX(2)
        app.setFont(13)

        app.addLabel('SInfoL', 'Information')
        app.getLabelWidget("SInfoL").config(font=("Comic Sans", "14", "bold"))

        # Name list
        aliasList = ["N/A"]
        app.addLabel('SNameL', 'Name:', row=1, column=0)
        aliasStr = ''
        for i, alias in enumerate(aliasList):
            aliasStr += alias + '\n'
        aliasStr = aliasStr[:-1]
        app.addMessage('SNameMsg', aliasStr, row=1, column=1)
        app.setMessageWidth('SNameMsg', conf['series_info_width'])
        rowCnt = 2

        # Author
        author = "N/A"
        app.addLabel('SAuthorL', 'Author:', row=rowCnt, column=0)
        app.addMessage('SAuthorMsg', author, row=rowCnt, column=1)
        app.setMessageWidth('SAuthorMsg', conf['series_info_width'])
        rowCnt += 1

        # Chapter
        app.addLabel('SChapterL', 'Total chapter:', row=rowCnt, column=0)
        app.addMessage('SChapterMsg', 'N/A', row=rowCnt, column=1)
        app.setMessageWidth('SChapterMsg', conf['series_info_width'])
        rowCnt += 1

        # State
        app.addLabel('SStateL', 'State:', row=rowCnt, column=0)
        app.addMessage('SStateMsg', 'N/A', row=rowCnt, column=1)
        app.setMessageWidth('SStateMsg', conf['series_info_width'])
        rowCnt += 1

        # Last updated
        # lastUpdated = 0
        # lastUpdatedStr = datetime.utcfromtimestamp(lastUpdated).strftime('%Y-%m-%d %H:%M:%S')
        app.addLabel('SLastUpdatedL', 'Last Updated:', row=rowCnt, column=0)
        app.addMessage('SLastUpdatedMsg', 'N/A', row=rowCnt, column=1)
        app.setMessageWidth('SLastUpdatedMsg', conf['series_info_width'])
        rowCnt += 1

        # Label
        labelList = ['N/A']
        labelStr = ''
        for l in labelList:
            labelStr += app.translate(l, '--') + ', '
        labelStr = labelStr[:-2]
        app.addLabel('SLabelL', 'Labels:', row=rowCnt, column=0)
        app.addMessage('SLabelMsg', labelStr, row=rowCnt, column=1)
        app.setMessageWidth('SLabelMsg', conf['series_info_width'])
        rowCnt += 1

        app.stopFrame()

        app.startFrame('SERIES_RRB', row=1, column=1)
        app.setSticky("NW")
        app.setPadX(2)
        app.setFont(13)

        # Intro
        intro = "N/A"
        app.addLabel('SIntroL', 'Introduction:', row=rowCnt, column=0)
        app.addMessage('SIntroMsg', intro, row=rowCnt, column=1)
        rowCnt += 1
        app.addLink('More...', self.loadFullSIntro, row=rowCnt, column=1)
        app.hideLink('More...')
        rowCnt += 1

        # Frame ends
        app.stopFrame()
        app.stopFrame()

        # Chpater list frame starts
        app.startFrame('SERIES_RIGHT', row=0, column=1)

        app.setSticky("NW")
        app.setStretch('ROW')
        app.setFg('black')

        app.addLabel("ChapterList", "Chapter List")
        app.addLabelOptionBox("ChapterStarts", ["N/A"])
        app.setOptionBoxChangeFunction("ChapterStarts", self.changeChapterStarts)
        app.startFrame("RRBB")
        app.setSticky("NW")
        for i in range(self.conf['chapters_per_page']):
            app.addLabel("Chapter_" + str(i), "")
            app.setLabelWidth("Chapter_" + str(i), 42)
            app.setLabelSubmitFunction("Chapter_" + str(i), self.onChapterClicked)
        app.stopFrame()
        app.stopFrame()

        app.stopSubWindow()
        # ============================

        # Bind keys
        app.bindKey("<Left>", self.loadPreviousManga)
        app.bindKey("<Right>", self.loadNextManga)
        app.bindKey("<a>", self.onMoveLeftBtnPressed)
        app.bindKey("<s>", self.onMoveDownBtnPressed)
        app.bindKey("<d>", self.onMoveRightBtnPressed)
        app.bindKey("<w>", self.onMoveUpBtnPressed)
        app.bindKey("<z>", self.onZoomInBtnPressed)
        app.bindKey("<x>", self.onZoomOutBtnPressed)
        app.bindKey("<Shift-Right>", self.loadNextChapter)
        app.bindKey("<Shift-Left>", self.loadPrevChapter)

    def __defaultCallback(self, name):
        print(name)

    def go(self, language=None):
        if language is None:
            self.language = self.getSetting('lang')
        else:
            self.language = language
        self.app.go(self.language)

    def displayLabelExample(self, btn):
        if btn == '%MangaName%':
            self.app.setLabel('LabelExampleL',
                              self.app.translate('MangaNameEx', '%MangaName%: Mange name(Domestic Girlfriend)'))
        elif btn == '%Order%':
            self.app.setLabel('LabelExampleL',
                              self.app.translate('OrderEx', '%Order%: Order in chapter list(1)'))
        elif btn == '%ChapterTitle%':
            self.app.setLabel('LabelExampleL',
                              self.app.translate('ChapterTitleEx',
                                                 '%ChapterTitle%: Chapter title(Vol.1 Chapter 1: I Want To Grow Up Soon)'))
        elif btn == '%DateTime%':
            self.app.setLabel('LabelExampleL',
                              self.app.translate('DateTimeEx', '%DateTime%: Current date&time(20190101123456)'))
        elif btn == '%JPMangaName%':
            self.app.setLabel('LabelExampleL',
                              self.app.translate('JPMangaName',
                                                 '%JPMangaName%: Manga Name in Japanese if exists(Beta)(ドメスティック彼女)'))

    def onLabelBtnPressed(self, btn):
        entry = self.app.getEntry('NamingEntry')
        self.app.setEntry('NamingEntry', entry + btn)

    def onSettingCancelPressed(self):
        self.app.hideSubWindow('Setting')

    def onDownloadCancelPressed(self):
        self.app.hideSubWindow('Download')

    def onOpenToolPressed(self, btn):
        path = self.app.directoryBox('Select Manga Directory')
        if path is not None:
            self.mangaPath = path
        else:
            return
        self.loadMangaDir()

    def updateNameMsg(self, name, aliasList):
        aliasStr = name + '\n'
        for i, alias in enumerate(aliasList):
            if alias != name:
                aliasStr += alias.strip() + '\n'
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
        lastUpdatedStr = datetime.utcfromtimestamp(lastUpdated).strftime('%Y-%m-%d %H:%M:%S')
        self.app.setMessage('LastUpdatedMsg', lastUpdatedStr)

    def updateLabelMsg(self, labelList):
        labelStr = ''
        for l in labelList:
            labelStr += l + ', '
        labelStr = labelStr[:-2]
        self.app.setMessage('LabelMsg', labelStr)

    def updateIntroMsg(self, intro):
        self.rrFrameHeight = self.app.getFrameWidget('RR').winfo_height()
        lineCnt = int((self.conf['manga_max_height'] - self.rrFrameHeight - 20) / 1.25 / 13)
        # print(self.rrFrameHeight, lineCnt)
        w = 35
        t = self.textWrap(intro, width=w, lineCnt=lineCnt)
        if t.endswith('...'):
            t = self.textWrap(intro, width=w, lineCnt=lineCnt - 1)
            self.app.showLink('More..')
        else:
            self.app.hideLink('More..')
        self.app.setMessage('IntroMsg', t)

    def loadMangaDir(self):
        self.app.setToolbarButtonEnabled("MD-fast-backward-alt")
        self.app.setToolbarButtonEnabled("MD-fast-forward-alt")
        self.app.setToolbarButtonEnabled("ZOOM-IN")
        self.app.setToolbarButtonEnabled("ZOOM-OUT")
        self.app.setToolbarButtonEnabled("REFRESH")
        self.app.setToolbarButtonEnabled("MD-REPEAT")
        self.app.setToolbarButtonEnabled("ARROW-1-LEFT")
        self.app.setToolbarButtonEnabled("ARROW-1-RIGHT")
        self.app.setToolbarButtonEnabled("ARROW-1-UP")
        self.app.setToolbarButtonEnabled("ARROW-1-DOWN")

        if not self.loadMangaMeta():
            return

        # Load the first image of this chapter
        self.currPage = 0
        self.mangaList = self.mangaMeta['manga_images_no_credit'] \
            if 'manga_images_no_credit' in self.mangaMeta and self.getSetting('ignore_credit') \
            else self.mangaMeta['manga_images']
        self.updateMangaImage(os.path.join(self.mangaPath, self.mangaMeta['manga_images'][0])) \
            if len(self.mangaMeta['manga_images']) > 0 else \
            self.app.warningBox('Warning', 'No Manga Image Found.')
        # Activate toolbar by manga list
        if len(self.mangaList) == 0 or len(self.mangaList) == 1:
            self.app.setToolbarButtonDisabled("MD-PREVIOUS")
            self.app.setToolbarButtonDisabled("MD-NEXT")
        else:
            self.app.setToolbarButtonDisabled("MD-PREVIOUS")
            self.app.setToolbarButtonEnabled("MD-NEXT")

        self.app.setStatusbar('%s %d / %d' %
                              (self.app.translate("ChapterSB", default="Chapter: "),
                               self.mangaMeta['current_chapter'], self.mangaMeta['total_chapters']), 0)
        self.app.setStatusbar('%s 1 / %d' % (self.app.translate("PageSB", "Page: "),
                                             len(self.mangaList)), 1)
        try:
            updatedAt = self.mangaMeta['chapters'][self.mangaMeta['current_chapter'] - 1]['updatedAt']
            updatedAtStr = datetime.utcfromtimestamp(updatedAt).strftime('%Y-%m-%d %H:%M:%S')
        except KeyError as e:
            updatedAtStr = 'N/A'
        self.app.setStatusbar('%s %s' % (self.app.translate("Updated atSB", "Updated at: "),
                                         updatedAtStr), 2)
        self.onReloadMetaPressed()

    def updateMangaImage(self, filepath):
        picImageData = self.readImage(filepath)
        self.app.setImageData('Manga', picImageData, fmt='PhotoImage')
        self.app.setStatusbar(self.app.translate("Zoom levelSB", "Zoom level: ") + ' ' +
                              str(self.zoomLevel), 3)
        self.app.setStatusbar("%s %d, %s %d" % (self.app.translate("Position LeftSB", "Position Left: "),
                                                self.leftOffset, self.app.translate("UpSB", " Up: "),
                                                self.upOffset), 4)

    def loadMangaMeta(self):
        try:
            with open(os.path.join(self.mangaPath, 'meta.json'), 'r') as f:
                metaObj = json.load(f)
        except FileNotFoundError as e:
            self.app.errorBox('Error', 'meta.json not exists')
            return False

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
        return True

    def loadFullIntro(self):
        self.app.infoBox('Introduction', self.mangaMeta['description'])

    def loadNextChapter(self):
        metaObj = self.mangaMeta
        if metaObj is None:
            return
        if metaObj['current_chapter'] == metaObj['total_chapters']:
            self.app.infoBox('Message', self.translate('LastChapterMsg', 'Already at the last chapter'))
            return

        dm = DataManager(os.path.join(self.getSetting('auto_download_dir'), 'data.db'))
        oid = metaObj['chapters'][metaObj['current_chapter']]['oid']
        chapterId = int(oid[oid.rfind('-') + 1:])
        chapter = dm.selectChapterByChapterId(chapterId)
        if chapter is None:
            self.downloadMangaURL = \
                'https://mangarock.com/manga/%s/chapter/%s' \
                % (metaObj['oid'],
                   metaObj['chapters'][metaObj['current_chapter']]['oid'])
            self.openDownloadWindow()
        else:
            self.mangaPath = chapter.getDirectory()
            self.loadMangaDir()

    def loadPrevChapter(self):
        metaObj = self.mangaMeta
        if metaObj is None:
            return
        if metaObj['current_chapter'] == 1:
            self.app.infoBox('Message', self.translate('LastChapterMsg', 'Already at the first chapter'))
            return

        dm = DataManager(os.path.join(self.getSetting('auto_download_dir'), 'data.db'))
        oid = metaObj['chapters'][metaObj['current_chapter'] - 2]['oid']
        chapterId = int(oid[oid.rfind('-') + 1:])
        chapter = dm.selectChapterByChapterId(chapterId)
        if chapter is None:
            self.downloadMangaURL = \
                'https://mangarock.com/manga/%s/chapter/%s' \
                % (metaObj['oid'], oid)
            self.openDownloadWindow()
        else:
            self.mangaPath = chapter.getDirectory()
            self.loadMangaDir()

    def loadNextManga(self):
        # print(self.currPage, len(self.mangaList), self.mangaList)
        if self.currPage == len(self.mangaList) - 1:
            if self.mangaMeta['current_chapter'] == self.mangaMeta['total_chapters']:
                # Already at the last page of manga
                self.app.infoBox('MangaRock Viewer', 'Already reach the last chapter. Thanks for your watching!')
            else:
                r = self.app.yesNoBox('MangaRock Viewer',
                                      'End of chapter: %s\n'
                                      'Would you want to load the next chapter?\n'
                                      'Next chapter: %s' % (
                                      self.mangaMeta['chapters'][self.mangaMeta['current_chapter'] - 1]['name'],
                                      self.mangaMeta['chapters'][self.mangaMeta['current_chapter']]['name']))
                if r:
                    self.loadNextChapter()
                return
        self.currPage += 1
        self.updateMangaImage(os.path.join(self.mangaPath, self.mangaList[self.currPage]))
        self.app.setStatusbar('%s %d / %d' % (self.app.translate("PageSB", "Page: "), self.currPage + 1,
                                              len(self.mangaList)), 1)
        self.app.setToolbarButtonEnabled("MD-PREVIOUS")
        if self.currPage == len(self.mangaList) - 1:
            self.app.setToolbarButtonDisabled("MD-NEXT")
        else:
            self.app.setToolbarButtonEnabled("MD-NEXT")

    def loadPreviousManga(self):
        if self.currPage == 0:
            return
        self.currPage -= 1
        self.updateMangaImage(os.path.join(self.mangaPath, self.mangaList[self.currPage]))
        self.app.setStatusbar('%s %d / %d' % (self.app.translate("PageSB", "Page: "), self.currPage + 1,
                                              len(self.mangaList)), 1)
        self.app.setToolbarButtonEnabled("MD-NEXT")
        if self.currPage == 0:
            self.app.setToolbarButtonDisabled("MD-PREVIOUS")
        else:
            self.app.setToolbarButtonEnabled("MD-PREVIOUS")

    def jumpMangaPage(self):
        isFirst = True
        while True:
            page = self.app.integerBox('Jump to...', '%s\nInput the page number(1-%d)'
                                       % ('Invalid page number!' if not isFirst else '',
                                          len(self.mangaMeta['manga_images'])))
            if page is not None and 0 < page <= len(self.mangaMeta['manga_images']):
                break
            elif page is None:
                return
            else:
                isFirst = False
        self.currPage = page - 1
        self.updateMangaImage(os.path.join(self.mangaPath, self.mangaMeta['manga_images'][self.currPage]))
        self.app.setStatusbar('%s %d / %d' % (self.app.translate("PageSB", "Page: "), self.currPage + 1,
                                              len(self.mangaList)), 1)

        if self.currPage == 0:
            self.app.setToolbarButtonDisabled("MD-PREVIOUS")
            self.app.setToolbarButtonEnabled("MD-NEXT")
        elif self.currPage == len(self.mangaList) - 1:
            self.app.setToolbarButtonEnabled("MD-PREVIOUS")
            self.app.setToolbarButtonDisabled("MD-NEXT")
        else:
            self.app.setToolbarButtonEnabled("MD-NEXT")
            self.app.setToolbarButtonEnabled("MD-PREVIOUS")

    def openAboutWindow(self):
        self.app.showSubWindow('About')

    def openHelpWindow(self):
        self.app.showSubWindow('Help')

    def openSettingWindow(self):
        self.app.showSubWindow('Setting')
        self.app.setRadioButton('lang', self.getSetting('lang'))
        self.app.setCheckBox('AutoCheckBox', ticked=self.getSetting('auto_download'))
        self.app.setEntry('AutoDownloadDir', self.getSetting('auto_download_dir'))
        self.app.setEntry('NamingEntry', self.getSetting('auto_download_naming'))

    def openDownloadWindow(self):
        if self.downloadMangaURL is not None:
            self.app.setEntry('MangaURLEntry', self.downloadMangaURL)
        if self.getSetting('auto_download'):
            self.app.setCheckBox('AutoDownloadCB', ticked=True)
            self.app.setLabelState('DirectoryL', 'disabled')
            self.app.setCheckBoxState('AutoDownloadCB', 'normal')
            self.app.setEntryState('DirectoryEntry', 'disabled')
        else:
            self.app.setCheckBox('AutoDownloadCB', ticked=False)
            # self.app.setLabelState('')
            self.app.setLabelState('DirectoryL', 'normal')
            self.app.setCheckBoxState('AutoDownloadCB', 'disabled')
            self.app.setEntryState('DirectoryEntry', 'normal')
        if self.downloadMangaURL is not None and self.getSetting('auto_download'):
            self.onDownloadOkPressed('DownloadOk')
        else:
            self.app.showSubWindow('Download')

    def onAutoDownloadDirChanged(self, event):
        if self.app.getCheckBox('AutoDownloadCB'):
            self.app.setLabelState('DirectoryL', 'disabled')
            self.app.setCheckBoxState('AutoDownloadCB', 'normal')
            self.app.setEntryState('DirectoryEntry', 'disabled')
        else:
            self.app.setLabelState('DirectoryL', 'normal')
            # self.app.setCheckBoxState('AutoDownloadCB', 'disabled')
            self.app.setEntryState('DirectoryEntry', 'normal')

    def generateAutoDownloadDir(self):
        dirFormat = self.getSetting('auto_download_naming')
        if '%JPMangaName%' in dirFormat:
            mn = MangaName()
            nameList = [self.mangaMeta['name']] + self.mangaMeta['alias']
            print([self.mangaMeta['name']], self.mangaMeta['alias'], nameList)
            s, r = mn.checkJPCN(nameList)
            print(s, r)
            dirFormat = dirFormat.replace('%JPMangaName%', r)
        dirFormat = dirFormat.replace('%MangaName%', self.mangaMeta['name'])
        dirFormat = dirFormat.replace('%Order%', str(self.mangaMeta['current_chapter']))
        dirFormat = dirFormat.replace('%ChapterTitle%',
                                      self.mangaMeta['chapters'][self.mangaMeta['current_chapter'] - 1]['name'])
        curTime = datetime.now().strftime('%Y%m%d%H%M%S')
        dirFormat = dirFormat.replace('%DateTime%', curTime)
        return dirFormat

    def onReloadMetaPressed(self):
        if self.mangaMeta is None:
            return
        chapterId = self.mangaMeta['chapters'][self.mangaMeta['current_chapter'] - 1]['oid']
        chapterId = chapterId[chapterId.rfind('-') + 1:]
        seriesId = self.mangaMeta['oid']
        seriesId = seriesId[seriesId.rfind('-') + 1:]
        self.downloadParam = {'url': '',
                              'chapterId': chapterId,
                              'seriesId': seriesId, 'directory': self.mangaPath}
        self.app.setStatusbar(self.translate('RefreshMetaMsg', 'Refreshing manga meta data...'), 5)
        self.isMetaReloading = True
        self.app.thread(self.downloadMetaData)

    def onDownloadOkPressed(self, btn):
        self.mriProgress.set(0)
        self.webpProgress.set(0)
        self.pngProgress.set(0)
        if self.downloadMangaURL is None:
            url = self.app.getEntry('MangaURLEntry').strip()
        else:
            url = self.downloadMangaURL.strip()
            self.downloadMangaURL = None
        if len(url) == 0:
            self.app.errorBox('Error', 'URL cannot be empty')
            return
        url = url[:url.rfind('?')] if url.rfind('?') != -1 else url
        url = url[:-1] if url.endswith('/') else url
        # directory is None means auto download
        directory = None
        if not self.app.getCheckBox('AutoDownloadCB'):
            directory = self.app.getEntry('DirectoryEntry')
            if directory is None or len(directory) == 0:
                self.app.errorBox('Error', 'Directory cannot be empty')
                return
        chapterId = url[url.rfind('mrs-chapter-') + len('mrs-chapter-'):]
        seriesId = url[url.rfind('mrs-serie-') + len('mrs-serie-'):url.rfind('/chapter')]
        self.downloadParam = {'url': url, 'chapterId': chapterId,
                              'seriesId': seriesId, 'directory': directory}
        # mr.getComicByChapter(chapterId, directory)
        self.app.setMessage('DPDownloadMsg0', self.app.translate('DPDownloadMsg0', 'Start downloading...'))
        self.app.setMessage('DPDownloadMsg1', self.app.translate('DPDownloadMsg1', 'Preprocessing...'))
        self.app.setMessage('DPDownloadMsg2', self.app.translate('DPDownloadMsg2', 'Meta data: --'))
        self.app.setMessage('DPDownloadMsg3', '')
        self.app.setMessage('DPDownloadMsg4', '')
        self.app.setMessage('DPDownloadMsg5', '')
        self.app.hideSubWindow('Download')
        self.app.showSubWindow('DownloadProgress')

        self.isDownloading = True
        # self.app.thread(self.downloadComic)
        self.app.thread(self.downloadComicMultiThread)

    def monitorThreadsProgress(self):
        n = len(self.mangaList)
        while True:
            mriProg = self.mriProgress.get()
            webpProg = self.webpProgress.get()
            pngProg = self.pngProgress.get()
            # print(n, mriProg, webpProg, pngProg)

            self.setDPMsg(3, self.app.translate('DownloadMRIMsg', 'Downloading MRI data: {0} / {1}').format(mriProg, n))
            self.setDPMsg(4, self.app.translate('ParseMRIMsg', 'Parsing MRI data: {0} / {1}').format(webpProg, n))
            self.setDPMsg(5, self.app.translate('ConvertPNGMsg', 'Convert to PNG: {0} / {1}').format(pngProg, n))
            if mriProg >= n and webpProg >= n and pngProg >= n:
                self.setDPMsg(3,
                              self.app.translate('DownloadMRIMsg', 'Downloading MRI data: {0} / {1}').format(mriProg, n)
                              + self.app.translate('DoneMsg', ". Done."))
                self.setDPMsg(4,
                              self.app.translate('ParseMRIMsg', 'Parsing MRI data: {0} / {1}').format(webpProg, n)
                              + self.app.translate('DoneMsg', ". Done."))
                self.setDPMsg(5,
                              self.app.translate('ConvertPNGMsg', 'Convert to PNG: {0} / {1}').format(pngProg, n)
                              + self.app.translate('DoneMsg', ". Done."))
                break
            time.sleep(1)

    def setDPMsg(self, position, content):
        if position not in [1, 2, 3, 4, 5]:
            print(content)
        else:
            msgTitle = 'DPDownloadMsg' + str(position)
            self.app.queueFunction(self.app.setMessage, msgTitle, content)

    # This method downloads manga with paralleling which is not fast enough
    def downloadComic(self):
        url = self.downloadParam['url']
        directory = self.downloadParam['directory']
        chapterId = self.downloadParam['chapterId']
        seriesId = self.downloadParam['seriesId']

        if not self.isDownloading:
            return

        if not os.path.exists(directory):
            self.setDPMsg(1, 'Directory %s not exists, so created...' % directory)
            try:
                os.mkdir(directory)
            except OSError:
                self.setDPMsg(1, "Creation of the directory failed")
            else:
                self.setDPMsg(1, "Successfully created the directory")

        mr = MangaRock()

        self.setDPMsg(2, 'Meta data: Get series information...')

        if not self.isDownloading:
            return
        metaObj = mr.getSeriesInfo(seriesId)

        if not self.isDownloading:
            return

        isValid = False
        for i, info in enumerate(metaObj['chapters']):
            if info['oid'] == 'mrs-chapter-' + str(chapterId):
                metaObj['current_chapter'] = i + 1
                isValid = True
                break

        if not self.isDownloading:
            return

        if not isValid:
            self.setDPMsg(2, 'Meta data: Invalid URL, this series does not have specific chapter.')
            return

        self.setDPMsg(2, 'Meta data: Series data, Done. ')

        self.setDPMsg(2, 'Meta data: Get meta data of chapter %s.' % chapterId)

        if not self.isDownloading:
            return

        mriList = mr.getMRIListByChapter(chapterId)
        metaObj['manga_images'] = ['ch' + str(chapterId) + '_' + str(i + 1) + '.png'
                                   for i in range(len(mriList))]

        self.setDPMsg(2, 'Meta data: Get chapter data, Done')

        if not self.isDownloading:
            return
        self.setDPMsg(2, 'Meta data: Write meta data...')
        with open(os.path.join(directory, 'meta.json'), 'w') as f:
            json.dump(metaObj, f)
        self.setDPMsg(2, 'Meta data: Write meta data, Done.')

        self.setDPMsg(3, 'Image processing: Get comic of chapter %s......' % chapterId)
        for i, mri in enumerate(mriList):
            if not self.isDownloading:
                return
            self.setDPMsg(3, 'Image processing: %d / %d' % (i + 1, len(mriList)))
            mriFile = os.path.join(directory, 'ch%s_%d.mri' % (chapterId, i + 1))
            webpFile = os.path.join(directory, 'ch%s_%d.webp' % (chapterId, i + 1))
            pngFile = os.path.join(directory, 'ch%s_%d.png' % (chapterId, i + 1))
            self.setDPMsg(3, 'Image processing: %d / %d, Get raw data...' % (i + 1, len(mriList)))
            mr.downloadMRI(mri, mriFile)
            if not self.isDownloading:
                return
            self.setDPMsg(3, 'Image processing: %d / %d, Parse raw data...' % (i + 1, len(mriList)))
            mr.mri2webp(mriFile, webpFile)
            self.setDPMsg(3, 'Image processing: %d / %d, Convert to png file...' % (i + 1, len(mriList)))
            mr.webp2png(webpFile, pngFile)
            self.setDPMsg(3, 'Image processing: %d / %d, Remove temporary files...' % (i + 1, len(mriList)))
            os.remove(mriFile)
            os.remove(webpFile)

        if not self.isDownloading:
            return
        self.isDownloading = False
        self.mangaPath = directory
        self.mangaMeta = metaObj
        self.mangaList = metaObj['manga_images']
        self.setDPMsg(3, 'Image processing: Get comic of chapter %s finished.' % (chapterId))
        self.app.setButton('DPBtn', 'Close')

    def writeMetaJSON(self, directory, metaObj):
        self.setDPMsg(2, self.app.translate('MetaWritingMsg',
                                            'Meta data: Write meta data...'))
        with open(os.path.join(directory, 'meta.json'), 'w') as f:
            json.dump(metaObj, f)
        self.setDPMsg(2, self.app.translate('MetaWriteDoneMsg',
                                            'Meta data: Write meta data, Done.'))

    def updateDatabase(self, chapterId, seriesId, directory, metaObj):
        current_time = int(time.time())
        dm = DataManager(os.path.join(self.getSetting('auto_download_dir'), 'data.db'))
        chapter = Chapter(None, int(chapterId), int(seriesId), directory, current_time,
                          current_time, metaObj['chapters'][metaObj['current_chapter'] - 1]['name'],
                          metaObj['chapters'][metaObj['current_chapter'] - 1]['updatedAt'])
        series = Series(None, seriesId, current_time, json.dumps(metaObj, ensure_ascii=False))
        if self.isDownloading and dm.selectChapterByChapterId(chapterId) is None:
            # Insert to database
            dm.insertChapter(chapter)
        else:
            # Update existed record
            dm.updateChapter(chapter)

        if self.isDownloading and dm.selectSeriesBySeriesId(seriesId) is None:
            dm.insertSeries(series)
        else:
            dm.updateSeries(series)

    def downloadMetaData(self):
        directory = self.downloadParam['directory']
        chapterId = self.downloadParam['chapterId']
        seriesId = self.downloadParam['seriesId']

        if not self.isDownloading and not self.isMetaReloading:
            return

        mr = MangaRock()
        metaObj = mr.getSeriesInfo(seriesId)
        if metaObj is None:
            self.app.queueFunction(self.app.setStatusbar,
                                   self.app.translate('RefreshMetaMsg') + self.app.translate('FailedMsg'),
                                   5)
            return

        isValid = False
        for i, info in enumerate(metaObj['chapters']):
            if info['oid'] == 'mrs-chapter-' + str(chapterId):
                metaObj['current_chapter'] = i + 1
                isValid = True
                break

        if not self.isDownloading and not self.isMetaReloading:
            return

        if not isValid:
            self.setDPMsg(2, self.app.translate('InvalidURLMsg',
                                                'Meta data: Invalid URL, this series does not have specific chapter.'))
            return

        mriList, mriListNoCredit = mr.getMRIListByChapter(chapterId)
        metaObj['manga_images'] = ['ch' + str(chapterId) + '_' + str(i + 1) + '.png'
                                   for i in range(len(mriList))]
        metaObj['manga_images_no_credit'] = ['ch' + str(chapterId) + '_' + str(i + 1) + '.png'
                                             for i in range(len(mriListNoCredit))]
        self.setDPMsg(2, self.app.translate('MetaDoneMsg',
                                            'Meta data: Get chapter data, Done'))

        if not self.isDownloading and not self.isMetaReloading:
            return
        if directory is not None:
            self.writeMetaJSON(directory, metaObj)

        if self.isMetaReloading:
            self.isMetaReloading = False
            self.app.queueFunction(self.app.setStatusbar,
                                   self.app.translate('RefreshMetaMsg') + self.app.translate('DoneMsg'),
                                   5)
            self.mangaMeta = metaObj
            self.loadMangaMeta()

        if self.getSetting('auto_download'):
            self.updateDatabase(chapterId, seriesId, directory, metaObj)

        return metaObj, mriList

    def createDir(self, directory):
        if not os.path.exists(directory):
            self.setDPMsg(1,
                          self.app.translate('DirectoryCreateMsg',
                                             'Directory {0} not exists, so created...').format(directory))
            try:
                os.mkdir(directory)
            except OSError:
                self.setDPMsg(1, self.app.translate('DirectoryCreateFailedMsg',
                                                    "Creation of the directory failed"))
            else:
                self.setDPMsg(1, self.app.translate('DirectoryCreatedMsg',
                                                    "Successfully created the directory"))

    def downloadComicMultiThread(self):
        url = self.downloadParam['url']
        directory = self.downloadParam['directory']
        chapterId = self.downloadParam['chapterId']
        seriesId = self.downloadParam['seriesId']

        if not self.isDownloading:
            return

        # If directory is not None, auto-downloading is not used
        # However, auto-downloading directory may be not created
        # Create directory if not exists
        if directory is not None:
            self.createDir(directory)
        else:
            self.createDir(self.getSetting('auto_download_dir'))

        if not self.isDownloading:
            return

        metaObj, mriList = self.downloadMetaData()
        self.mangaMeta = metaObj
        # Auto-downloading is used, directory is based on metaObj
        if directory is None:
            folder = self.generateAutoDownloadDir()
            print(folder)
            directory = os.path.join(self.getSetting('auto_download_dir'), folder)
            self.createDir(directory)
            self.writeMetaJSON(directory, metaObj)
            self.updateDatabase(chapterId, seriesId, directory, metaObj)

        self.mangaPath = directory

        if 14 in metaObj['categories'] and \
                not self.app.questionBox(self.app.translate('AgeConfirmationTitle'),
                                         self.app.translate('AgeConfirmationBox')):
            self.onDPBtnPressed(None)
            return

        jobQueue = Queue()
        mriQueue = Queue()
        webpQueue = Queue()
        tempFileQueue = Queue()
        self.mangaList = metaObj['manga_images']
        self.app.thread(self.monitorThreadsProgress)
        for i, mri in enumerate(mriList):
            mriFile = os.path.join(directory, 'ch%s_%d.mri' % (chapterId, i + 1))
            webpFile = os.path.join(directory, 'ch%s_%d.webp' % (chapterId, i + 1))
            pngFile = os.path.join(directory, 'ch%s_%d.png' % (chapterId, i + 1))
            jobQueue.put((mri, mriFile, webpFile, pngFile))

        mriThread = MRIThread(1, jobQueue, mriQueue, gui=self)
        mriThread1 = MRIThread(2, jobQueue, mriQueue, gui=self)
        parseMRIThread = ParseMRIThread(1, mriQueue, webpQueue, tempFileQueue=tempFileQueue, gui=self)
        pngThread = PNGThread(1, webpQueue, tempFileQueue=tempFileQueue, gui=self)
        pngThread1 = PNGThread(2, webpQueue, tempFileQueue=tempFileQueue, gui=self)
        mriThread.start()
        time.sleep(1)
        mriThread1.start()
        parseMRIThread.start()
        pngThread.start()
        time.sleep(1)
        pngThread1.start()

        tempFileThread = TempFileThread(1, tempFileQueue)
        tempFileThread.start()
        self.threads = [mriThread, mriThread1, parseMRIThread, pngThread, pngThread1, tempFileThread]

        tempFileThread.join()
        self.isDownloading = False

        # self.mangaList = metaObj['manga_images']
        # self.setDPMsg(3, 'Image processing: Get comic of chapter %s finished.' % (chapterId))
        self.app.setButton('DPBtn', 'Close')
        print('Get comic of chapter %s finished.' % chapterId)

    def onDownloadCancelPressed(self, btn):
        self.app.hideSubWindow('Download')

    def onDPBtnPressed(self, btn):
        if self.isDownloading:
            # Force Quit is clicked
            if self.app.yesNoBox('Warning', 'Do you want to quit?'):
                self.isDownloading = False
                for th in self.threads:
                    th.stop()
            else:
                return
        else:
            # Close is clicked
            # Load content to pic
            self.loadMangaDir()
        self.app.hideSubWindow('DownloadProgress')

    # def writeDownloadMsg(self, message):
    #     message0 = self.app.getMessage('DPDownloadMsg')
    #     self.app.setMessage('DPDownloadMsg', message0 + '\n' + message0)

    def onZoomInBtnPressed(self, btn):
        if self.zoomLevel <= 10:
            self.zoomLevel += 1
            self.updateMangaImage(os.path.join(self.mangaPath, self.mangaMeta['manga_images'][self.currPage]))

    def onZoomOutBtnPressed(self, btn):
        if self.zoomLevel > 0:
            self.zoomLevel -= 1
            self.updateMangaImage(os.path.join(self.mangaPath, self.mangaMeta['manga_images'][self.currPage]))

    def onMoveLeftBtnPressed(self, btn):
        self.leftOffset += 50
        self.updateMangaImage(os.path.join(self.mangaPath, self.mangaMeta['manga_images'][self.currPage]))

    def onMoveRightBtnPressed(self, btn):
        self.leftOffset -= 50
        self.updateMangaImage(os.path.join(self.mangaPath, self.mangaMeta['manga_images'][self.currPage]))

    def onMoveUpBtnPressed(self, btn):
        self.upOffset += 50
        self.updateMangaImage(os.path.join(self.mangaPath, self.mangaMeta['manga_images'][self.currPage]))

    def onMoveDownBtnPressed(self, btn):
        self.upOffset -= 50
        self.updateMangaImage(os.path.join(self.mangaPath, self.mangaMeta['manga_images'][self.currPage]))

    def onImageSizeChanged(self, event):
        self.conf['manga_max_width'] = max(560, event.width)
        self.conf['manga_max_height'] = max(660, event.height)
        if self.mangaMeta is not None:
            self.updateMangaImage(os.path.join(self.mangaPath, self.mangaMeta['manga_images'][self.currPage]))
        else:
            self.updateMangaImage('./intro.png')
        if self.mangaMeta is not None:
            self.updateIntroMsg(self.mangaMeta['description'])

    def onSettingUpdateBtnPressed(self, btn):
        self.language = self.app.getRadioButton('lang')
        self.putSetting('lang', self.language)
        self.putSetting('auto_download', self.app.getCheckBox('AutoCheckBox'))
        self.putSetting('auto_download_dir', self.app.getEntry('AutoDownloadDir'))
        self.putSetting('auto_download_naming', self.app.getEntry('NamingEntry'))
        if self.getSetting('auto_download') and \
                (self.getSetting('auto_download_dir') == "" or
                 self.getSetting('auto_download_naming') == ""):
            self.app.errorBox('Error', 'Directory and Naming format must be filled!')
            return
        self.writeSettings()
        self.app.hideSubWindow('Setting')
        self.app.changeLanguage(self.language)
        self.changeLanguage(self.language)
        if self.mangaMeta is not None:
            self.loadMangaMeta()

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

    # =====================

    def loadFullSIntro(self):
        self.app.infoBox('Introduction', self.seriesMeta['description'])

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
        self.updateSNameMsg('N/A', ['N/A'])
        self.updateSAuthorMsg('N/A')
        self.updateSChapterMsg('N/A')
        self.updateSStateMsg('N/A')
        labelList = ['N/A']
        self.updateSLabelMsg(labelList)
        self.updateSLastUpdatedMsg('N/A')
        self.updateSIntroMsg('N/A')

        self.app.changeOptionBox('ChapterStarts', ['N/A'])
        for i in range(self.conf["chapters_per_page"]):
            self.app.setLabel("Chapter_" + str(i), "")

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
        self.seriesMeta = metaObj
        self.updateSNameMsg(metaObj['name'], metaObj['alias'])
        self.updateSAuthorMsg(metaObj['author'])
        self.updateSChapterMsg(metaObj['total_chapters'])
        self.updateSStateMsg(metaObj['completed'])
        labelList = []
        for label in metaObj['rich_categories']:
            labelList.append(self.app.translate(label['name'], '--'))
        self.updateSLabelMsg(labelList)
        self.updateSLastUpdatedMsg(metaObj['last_update'])
        self.updateSIntroMsg(metaObj['description'])

        newChapterStarts = list(range(1, len(metaObj['chapters']), self.conf["chapters_per_page"]))
        if len(newChapterStarts) == 0:
            newChapterStarts = ['N/A']
        self.app.changeOptionBox('ChapterStarts', newChapterStarts)
        self.loadChapterList()

    def loadChapterList(self):
        if self.app.getOptionBox('ChapterStarts') == 'N/A':
            return
        self.chapterStart = int(self.app.getOptionBox('ChapterStarts'))
        # Load chapters from chapterStarts-1 to chapterStarts-1+self.conf["chapters_per_page"]
        for i in range(min(self.conf["chapters_per_page"],
                           len(self.seriesMeta['chapters']) - self.chapterStart)):
            idx = self.chapterStart - 1 + i
            name = self.seriesMeta['chapters'][idx]['name']
            if len(name) > 50:
                name = name[:47] + "..."
            self.app.setLabel("Chapter_" + str(i), name)

        for i in range(min(self.conf["chapters_per_page"],
                           len(self.seriesMeta['chapters']) - self.chapterStart), self.conf["chapters_per_page"]):
            self.app.setLabel("Chapter_" + str(i), "")

    def updateSNameMsg(self, name, aliasList):
        aliasStr = name + '\n'
        for i, alias in enumerate(aliasList):
            if i > 5:
                break
            if alias != name:
                aliasStr += alias.strip() + ';\n'
        aliasStr = aliasStr[:-1]
        self.app.setMessage('SNameMsg', aliasStr)

    def updateSAuthorMsg(self, author):
        self.app.setMessage('SAuthorMsg', author)

    def updateSChapterMsg(self, totalChapter):
        self.app.setMessage('SChapterMsg', totalChapter)

    def updateSStateMsg(self, isCompleted):
        self.app.setMessage('SStateMsg',
                            self.app.translate('CompletedMsg', "Completed")
                            if isCompleted else self.app.translate('OngoingMsg', "Ongoing"))

    def updateSLastUpdatedMsg(self, lastUpdated):
        if type(lastUpdated) == int:
            lastUpdatedStr = datetime.utcfromtimestamp(lastUpdated).strftime('%Y-%m-%d %H:%M:%S')
        else:
            lastUpdatedStr = lastUpdated
        self.app.setMessage('SLastUpdatedMsg', lastUpdatedStr)

    def updateSLabelMsg(self, labelList):
        labelStr = ''
        for l in labelList:
            labelStr += l + ', '
        labelStr = labelStr[:-2]
        self.app.setMessage('SLabelMsg', labelStr)

    def updateSIntroMsg(self, intro):
        lineCnt = 12
        # print(self.rrFrameHeight, lineCnt)
        w = 42
        t = self.textWrap(intro, width=w, lineCnt=lineCnt)
        if t.endswith('...'):
            t = self.textWrap(intro, width=w, lineCnt=lineCnt - 1)
            self.app.showLink('More...')
        else:
            self.app.hideLink('More...')
        self.app.setMessage('SIntroMsg', t)

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

    def onSearchPressed(self, ev):
        self.app.showSubWindow('Search')

    def onChapterClicked(self, btn):
        idx = int(btn[btn.rfind('_')+1:])
        obj = self.seriesMeta['chapters'][self.chapterStart + idx]
        url = 'https://mangarock.com/manga/%s/chapter/%s' % (self.seriesMeta['oid'], obj['oid'])
        self.app.setEntry('MangaURLEntry', url)
        self.app.hideSubWindow('Search')
        self.app.hideSubWindow('Series')
        self.openDownloadWindow()


if __name__ == '__main__':
    mv = MangaViewer()
    mv.go()
