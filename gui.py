from appJar import gui
from PIL import Image, ImageTk
from datetime import datetime
import json
import os
import sys


class MangaViewer:
    def __init__(self):
        self.conf = {'width': 900, 'height': 740,
                     'manga_max_width': 560, 'manga_max_height': 660,
                     'manga_bg': 'black', 'info_width': 200,
                     }
        self.app = gui("FRAME DEMO", "%dx%d" % (self.conf['width'], self.conf['height']))
        self.mangaPath = './'
        self.nameMsgTitle = []
        self.mangaMeta = {}
        self.currPage = -1  # starting from 0
        self.mangaList = []
        self.__setLayout()

    def readImage(self, filepath):
        conf = self.conf
        oriImg = Image.open(filepath)
        ratio = conf['manga_max_height'] / oriImg.size[1] if oriImg.size[1] > oriImg.size[0] else \
            conf['manga_max_width'] / oriImg.size[0]
        ratio = 1 if oriImg.size[0] < conf['manga_max_width'] and \
                     oriImg.size[1] < conf['manga_max_height'] else ratio
        newSize = (int(oriImg.size[0] * ratio), int(oriImg.size[1] * ratio))
        image0 = oriImg.resize(newSize, Image.ANTIALIAS)
        img = ImageTk.PhotoImage(image0)
        return img

    def __setLayout(self):
        app = self.app
        conf = self.conf

        app.setBg(conf['manga_bg'])
        app.setFg('lightgray')

        tools = ["OPEN", "DOWNLOAD", "REFRESH", "MD-PREVIOUS", "MD-NEXT", "MD-REPEAT",
                 "ZOOM-IN", "ZOOM-OUT",
                 "ARROW-1-LEFT", "ARROW-1-RIGHT", "ARROW-1-UP",
                 "ARROW-1-DOWN", "SETTINGS", "HELP", "ABOUT", "OFF"]
        funcs = [self.onOpenToolPressed, self.__defaultCallback, self.__defaultCallback,
                 self.loadPreviousManga, self.loadNextManga, self.jumpMangaPage,
                 self.__defaultCallback, self.__defaultCallback, self.__defaultCallback,
                 self.__defaultCallback, self.__defaultCallback, self.__defaultCallback,
                 self.__defaultCallback, self.openHelpWindow, self.openAboutWindow,
                 self.app.stop]

        app.addToolbar(tools, funcs, findIcon=True)

        # app.setToolbarButtonDisabled("OPEN")
        app.setToolbarButtonDisabled("DOWNLOAD")
        app.setToolbarButtonDisabled("REFRESH")
        app.setToolbarButtonDisabled("MD-PREVIOUS")
        app.setToolbarButtonDisabled("MD-NEXT")
        app.setToolbarButtonDisabled("ZOOM-IN")
        app.setToolbarButtonDisabled("ZOOM-OUT")
        app.setToolbarButtonDisabled("ARROW-1-LEFT")
        app.setToolbarButtonDisabled("ARROW-1-RIGHT")
        app.setToolbarButtonDisabled("ARROW-1-UP")
        app.setToolbarButtonDisabled("ARROW-1-DOWN")
        app.setToolbarButtonDisabled("SETTINGS")
        # app.setToolbarButtonDisabled("HELP")
        # app.setToolbarButtonDisabled("ABOUT")

        app.startFrame("LEFT", row=0, column=0, rowspan=1, colspan=2)
        app.setBg(conf['manga_bg'])
        app.setSticky("NEWS")
        app.setStretch("BOTH")

        app.addImageData('Manga', self.readImage('./1.png'), fmt='PhotoImage')
        app.setImageSize('Manga', conf['manga_max_width'], conf['manga_max_height'])
        app.stopFrame()

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
            labelStr += l + ', '
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
        app.addStatusbar(fields=3)
        app.setStatusbar("Chapter: N/A", 0)
        app.setStatusbar("Page: N/A", 1)
        app.setStatusbar("Updated at: N/A", 2)

        # Help dialog
        app.startSubWindow("Help", modal=True)
        app.setFg('black')
        app.setSize(480, 620)
        app.setSticky('NW')
        app.setPadX(10)
        app.addIcon('Open manga directory', 'OPEN', compound='left')
        app.addIcon('Download manga chapter from MangaRock', 'DOWNLOAD', compound='left')
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
        app.setMessageWidth('AboutContentMsg', 450)

        # set the button's name to match the SubWindow's name
        app.addNamedButton("Close", "About", app.hideSubWindow)
        app.stopSubWindow()

    def __defaultCallback(self, name):
        print(name)

    def go(self):
        self.app.go()

    def onOpenToolPressed(self, btn):
        self.mangaPath = self.app.directoryBox('Select Manga Directory')
        self.loadMangaDir()

    def updateNameMsg(self, aliasList):
        aliasStr = ''
        for i, alias in enumerate(aliasList):
            aliasStr += alias.strip() + '\n'
        aliasStr = aliasStr[:-1]
        self.app.setMessage('NameMsg', aliasStr)

    def updateAuthorMsg(self, author):
        self.app.setMessage('AuthorMsg', author)

    def updateChapterMsg(self, totalChapter):
        self.app.setMessage('ChapterMsg', totalChapter)

    def updateStateMsg(self, isCompleted):
        self.app.setMessage('StateMsg', "Completed" if isCompleted else "Ongoing")

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
        self.loadMangaMeta()
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

        self.app.setStatusbar('Chapter: %d / %d' %
                              (self.mangaMeta['current_chapter'], self.mangaMeta['total_chapters']), 0)
        self.app.setStatusbar('Page: 1 / %d' % len(self.mangaMeta['manga_images']), 1)
        try:
            updatedAt = self.mangaMeta['chapters'][self.mangaMeta['current_chapter'] - 1]['updatedAt']
            updatedAtStr = datetime.utcfromtimestamp(updatedAt).strftime('%Y-%m-%d %H:%M:%S')
        except KeyError as e:
            updatedAtStr = 'N/A'
        self.app.setStatusbar('Updated at: %s' % updatedAtStr, 2)
        self.app.debug("User %s, has accessed the app from %s", '1', '2')

    def updateMangaImage(self, filepath):
        picImageData = self.readImage(filepath)
        self.app.setImageData('Manga', picImageData, fmt='PhotoImage')

    def loadMangaMeta(self):
        with open(os.path.join(self.mangaPath, 'meta.json'), 'r') as f:
            metaObj = json.load(f)

        self.mangaMeta = metaObj

        self.updateNameMsg(metaObj['alias'])
        self.updateAuthorMsg(metaObj['author'])
        self.updateChapterMsg(metaObj['total_chapters'])
        self.updateStateMsg(metaObj['completed'])
        labelList = []
        for label in metaObj['rich_categories']:
            labelList.append(label['name'])
        self.updateLabelMsg(labelList)
        self.updateLastUpdatedMsg(metaObj['last_update'])
        self.updateIntroMsg(metaObj['description'])

    def loadNextManga(self):
        if self.currPage == len(self.mangaList) - 1:
            return
        self.currPage += 1
        self.updateMangaImage(os.path.join(self.mangaPath, self.mangaMeta['manga_images'][self.currPage]))
        self.app.setStatusbar('Page: %d / %d'
                              % (self.currPage + 1, len(self.mangaMeta['manga_images'])), 1)
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
        self.app.setStatusbar('Page: %d / %d'
                              % (self.currPage + 1, len(self.mangaMeta['manga_images'])), 1)
        self.app.setToolbarButtonEnabled("MD-NEXT")
        if self.currPage == 0:
            self.app.setToolbarButtonDisabled("MD-PREVIOUS")
        else:
            self.app.setToolbarButtonEnabled("MD-PREVIOUS")

    def jumpMangaPage(self):
        isFirst = True
        while True:
            page = self.app.integerBox('Jump to...', '%s\nInput the page number(1-%d)'
                                       % ('Invalid page number!',
                                          len(self.mangaMeta['manga_images'])))
            if 0 < page <= len(self.mangaMeta['manga_images']):
                break
        self.currPage = page - 1
        self.updateMangaImage(os.path.join(self.mangaPath, self.mangaMeta['manga_images'][self.currPage]))
        self.app.setStatusbar('Page: %d / %d'
                              % (self.currPage + 1, len(self.mangaMeta['manga_images'])), 1)

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


if __name__ == '__main__':
    mv = MangaViewer()
    mv.go()
