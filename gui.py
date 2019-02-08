from appJar import gui
from PIL import Image, ImageTk
from datetime import datetime
import json
import os
import time
import codecs
from main import *
from multiprocessing import Queue


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


class MangaViewer:
    def __init__(self, language="ENGLISH"):
        self.conf = {'width': 900, 'height': 740,
                     'manga_max_width': 560, 'manga_max_height': 660,
                     'manga_bg': 'black', 'info_width': 200,
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
                                                  len(self.mangaMeta['manga_images'])), 1)
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

        tools = ["DOWNLOAD", "OPEN", "REFRESH", "MD-PREVIOUS", "MD-NEXT", "MD-REPEAT",
                 "ZOOM-IN", "ZOOM-OUT",
                 "ARROW-1-LEFT", "ARROW-1-RIGHT", "ARROW-1-UP",
                 "ARROW-1-DOWN", "SETTINGS", "HELP", "ABOUT", "OFF"]
        funcs = [self.openDownloadWindow, self.onOpenToolPressed, self.onReloadMetaPressed,
                 self.loadPreviousManga, self.loadNextManga, self.jumpMangaPage,
                 self.onZoomInBtnPressed, self.onZoomOutBtnPressed, self.onMoveLeftBtnPressed,
                 self.onMoveRightBtnPressed, self.onMoveUpBtnPressed, self.onMoveDownBtnPressed,
                 self.openSettingWindow, self.openHelpWindow, self.openAboutWindow,
                 self.app.stop]

        app.addToolbar(tools, funcs, findIcon=True)

        # app.setToolbarButtonDisabled("OPEN")
        # app.setToolbarButtonDisabled("DOWNLOAD")
        # app.setToolbarButtonDisabled("REFRESH")
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
        app.setPadX(5)
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

        # Intro
        intro = "N/A"
        app.addLabel('IntroL', 'Introduction:', row=rowCnt, column=0)
        app.addMessage('IntroMsg', intro, row=rowCnt, column=1)
        app.setMessageWidth('IntroMsg', conf['info_width'])
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
        app.setStatusbarWidth(5, 0)
        app.setStatusbarWidth(5, 1)
        app.setStatusbarWidth(5, 3)
        app.setStatusbarWidth(10, 2)
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
        app.setSize(480, 200)
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
        app.addLabel('DirectoryL', 'Directory')
        app.addDirectoryEntry("DirectoryEntry", row=1, column=1)
        app.setFocus("MangaURLEntry")

        # set the button's name to match the SubWindow's name
        app.addNamedButton("Cancel", "DownloadCancel", self.onDownloadCancelPressed, 2, 0, 1)
        app.addNamedButton("OK", "DownloadOk", self.onDownloadOkPressed, 2, 1, 1)
        app.stopSubWindow()

        # Setting dialog
        app.startSubWindow("Setting", modal=True)
        app.setFg('black')
        app.setSize(480, 200)
        app.setSticky('NW')
        app.setFont(14)
        app.setPadX(10)
        app.setPadY(10)

        app.startLabelFrame("Language")
        app.addRadioButton("lang", "ENGLISH")
        app.addRadioButton("lang", "简体中文")
        app.stopLabelFrame()

        # set the button's name to match the SubWindow's name
        app.addButtons(["Update", "Cancel"],
                       [self.onSettingUpdateBtnPressed, self.onSettingCancelPressed], 2, 0, 2)
        # app.addNamedButton("Cancel", "SettingCancel", app.hideSubWindow, row=2, column=0)
        # app.addNamedButton("OK", "SettingOk", self.onDownloadOkPressed, row=2, column=1)
        app.stopSubWindow()

        # Bind keys
        app.bindKey("<Left>", self.loadPreviousManga)
        app.bindKey("<Right>", self.loadNextManga)
        app.bindKey("<a>", self.onMoveLeftBtnPressed)
        app.bindKey("<s>", self.onMoveDownBtnPressed)
        app.bindKey("<d>", self.onMoveRightBtnPressed)
        app.bindKey("<w>", self.onMoveUpBtnPressed)
        app.bindKey("<z>", self.onZoomInBtnPressed)
        app.bindKey("<x>", self.onZoomOutBtnPressed)

    def __defaultCallback(self, name):
        print(name)

    def go(self, language=None):
        if language is None:
            self.language = self.getSetting('lang')
        else:
            self.language = language
        self.app.go(self.language)

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
        aliasStr = name+'\n'
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
        self.app.setMessage('IntroMsg', intro)

    def loadMangaDir(self):
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
        self.mangaList = self.mangaMeta['manga_images']
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
                                             len(self.mangaMeta['manga_images'])), 1)
        try:
            updatedAt = self.mangaMeta['chapters'][self.mangaMeta['current_chapter'] - 1]['updatedAt']
            updatedAtStr = datetime.utcfromtimestamp(updatedAt).strftime('%Y-%m-%d %H:%M:%S')
        except KeyError as e:
            updatedAtStr = 'N/A'
        self.app.setStatusbar('%s %s' % (self.app.translate("Updated atSB", "Updated at: "),
                                         updatedAtStr), 2)
        self.app.debug("User %s, has accessed the app from %s", '1', '2')

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

    def loadNextManga(self):
        if self.currPage == len(self.mangaList) - 1:
            return
        self.currPage += 1
        self.updateMangaImage(os.path.join(self.mangaPath, self.mangaMeta['manga_images'][self.currPage]))
        self.app.setStatusbar('%s %d / %d' % (self.app.translate("PageSB", "Page: "), self.currPage + 1,
                                              len(self.mangaMeta['manga_images'])), 1)
        self.app.setToolbarButtonEnabled("MD-PREVIOUS")
        if self.currPage == len(self.mangaList) - 1:
            self.app.setToolbarButtonDisabled("MD-NEXT")
        else:
            self.app.setToolbarButtonEnabled("MD-NEXT")

    def loadPreviousManga(self):
        if self.currPage == 0:
            return
        self.currPage -= 1
        self.updateMangaImage(os.path.join(self.mangaPath, self.mangaMeta['manga_images'][self.currPage]))
        self.app.setStatusbar('%s %d / %d' % (self.app.translate("PageSB", "Page: "), self.currPage + 1,
                                              len(self.mangaMeta['manga_images'])), 1)
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
            else:
                isFirst = False
        self.currPage = page - 1
        self.updateMangaImage(os.path.join(self.mangaPath, self.mangaMeta['manga_images'][self.currPage]))
        self.app.setStatusbar('%s %d / %d' % (self.app.translate("PageSB", "Page: "), self.currPage + 1,
                                              len(self.mangaMeta['manga_images'])), 1)

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

    def openDownloadWindow(self):
        self.app.showSubWindow('Download')

    def onReloadMetaPressed(self):
        if self.mangaMeta is None or len(self.mangaList) == 0:
            return
        chapterId = self.mangaMeta['chapters'][self.mangaMeta['current_chapter']-1]['oid']
        chapterId = chapterId[chapterId.rfind('-')+1:]
        seriesId = self.mangaMeta['oid']
        seriesId = seriesId[seriesId.rfind('-')+1:]
        self.downloadParam = {'url': '',
                              'chapterId': chapterId,
                              'seriesId': seriesId, 'directory': self.mangaPath}
        self.app.setStatusbar(self.translate('RefreshMetaMsg', 'Refreshing manga meta data...'), 5)
        self.isMetaReloading = True
        self.app.thread(self.downloadMetaData)

    def onDownloadOkPressed(self, btn):
        url = self.app.getEntry('MangaURLEntry').strip()
        if len(url) == 0:
            self.app.errorBox('Error', 'URL cannot be empty')
            return
        url = url[:url.rfind('?')] if url.rfind('?') != -1 else url
        url = url[:-1] if url.endswith('/') else url
        directory = self.app.getEntry('DirectoryEntry')
        if len(directory) == 0:
            self.app.errorBox('Error', 'Directory cannot be empty')
            return
        chapterId = url[url.rfind('mrs-chapter-') + len('mrs-chapter-'):]
        seriesId = url[url.rfind('mrs-serie-') + len('mrs-serie-'):url.rfind('/chapter')]
        self.downloadParam = {'url': url, 'chapterId': chapterId,
                              'seriesId': seriesId, 'directory': directory}
        # mr.getComicByChapter(chapterId, directory)
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

    def downloadMetaData(self):
        directory = self.downloadParam['directory']
        chapterId = self.downloadParam['chapterId']
        seriesId = self.downloadParam['seriesId']

        if not self.isDownloading and not self.isMetaReloading:
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
        metaObj = mr.getSeriesInfo(seriesId)

        isValid = False
        for i, info in enumerate(metaObj['chapters']):
            if info['oid'] == 'mrs-chapter-' + str(chapterId):
                metaObj['current_chapter'] = i + 1
                isValid = True
                break

        if not self.isDownloading and not self.isMetaReloading:
            return

        if not isValid:
            self.setDPMsg(2, 'Meta data: Invalid URL, this series does not have specific chapter.')
            return

        mriList = mr.getMRIListByChapter(chapterId)
        metaObj['manga_images'] = ['ch' + str(chapterId) + '_' + str(i + 1) + '.png'
                                   for i in range(len(mriList))]
        self.setDPMsg(2, 'Meta data: Get chapter data, Done')

        if not self.isDownloading and not self.isMetaReloading:
            return
        self.setDPMsg(2, 'Meta data: Write meta data...')
        with open(os.path.join(directory, 'meta.json'), 'w') as f:
            json.dump(metaObj, f)
        self.setDPMsg(2, 'Meta data: Write meta data, Done.')
        if self.isMetaReloading:
            self.isMetaReloading = False
            self.app.queueFunction(self.app.setStatusbar,
                                   self.app.translate('RefreshMetaMsg')+self.app.translate('DoneMsg'),
                                   5)
            self.loadMangaMeta()
        return metaObj, mriList

    def downloadComicMultiThread(self):
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

        metaObj, mriList = self.downloadMetaData()

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
        self.mangaPath = directory
        self.mangaMeta = metaObj
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

    def writeDownloadMsg(self, message):
        message0 = self.app.getMessage('DPDownloadMsg')
        self.app.setMessage('DPDownloadMsg', message0 + '\n' + message0)

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

    def onSettingUpdateBtnPressed(self, btn):
        self.language = self.app.getRadioButton('lang')
        self.putSetting('lang', self.language)
        self.writeSettings()
        self.app.hideSubWindow('Setting')
        self.app.changeLanguage(self.language)
        self.changeLanguage(self.language)
        if self.mangaMeta is not None:
            self.loadMangaMeta()


if __name__ == '__main__':
    mv = MangaViewer()
    mv.go()
