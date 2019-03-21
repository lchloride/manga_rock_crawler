from appJar import gui
from PIL import Image, ImageTk
from datetime import datetime
import json
import os
import time
import codecs
from main import *
from data import *
from multiprocessing import Queue
import textwrap


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
        self.conf = {'width': 950, 'height': 740,
                     'manga_max_width': 560, 'manga_max_height': 660,
                     'manga_bg': 'black', 'info_width': 225,
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

        tools = ["DOWNLOAD", "OPEN", "REFRESH", "MD-fast-backward-alt", "MD-fast-forward-alt",
                 "MD-PREVIOUS", "MD-NEXT", "MD-REPEAT",
                 "ZOOM-IN", "ZOOM-OUT",
                 "ARROW-1-LEFT", "ARROW-1-RIGHT", "ARROW-1-UP",
                 "ARROW-1-DOWN", "SETTINGS", "HELP", "ABOUT", "OFF"]
        funcs = [self.openDownloadWindow, self.onOpenToolPressed, self.onReloadMetaPressed,
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
                self.app.infoBox('MangaRock Viewer','Already reach the last chapter. Thanks for your watching!')
            else:
                r = self.app.yesNoBox('MangaRock Viewer',
                              'End of chapter: %s\n'
                              'Would you want to load the next chapter?\n'
                              'Next chapter: %s' % (self.mangaMeta['chapters'][self.mangaMeta['current_chapter']-1]['name'],
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
        self.app.setMessage('DPDownloadMsg0', self.app.translate('DPDownloadMsg0','Start downloading...'))
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
        # Create directory if not exists
        if directory is not None:
            self.createDir(directory)

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


if __name__ == '__main__':
    mv = MangaViewer()
    mv.go()
