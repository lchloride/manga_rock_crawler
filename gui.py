from appJar import gui
from PIL import Image, ImageTk
from datetime import datetime
import json
import os
import sys


class MangaViewer:
    def __init__(self):
        self.conf = {'width': 900, 'height': 740,
                     'manga_max_width': 540, 'manga_max_height': 660,
                     'manga_bg': 'black', 'info_width': 200,
                     }
        self.app = gui("FRAME DEMO", "%dx%d" % (self.conf['width'], self.conf['height']))
        self.mangaPath = './'
        self.nameMsgTitle = []
        self.__setLayout()

    def readImage(self, filepath):
        conf = self.conf
        oriImg = Image.open(filepath)
        print(oriImg.size)
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

        app.setBg("yellow")

        tools = ["OPEN", "DOWNLOAD", "REFRESH", "MD-PREVIOUS", "MD-NEXT", "MD-REPEAT",
                 "ZOOM-IN", "ZOOM-OUT",
                 "ARROW-1-LEFT", "ARROW-1-RIGHT", "ARROW-1-UP",
                 "ARROW-1-DOWN", "SETTINGS", "HELP", "ABOUT", "OFF"]
        funcs = [self.onOpenToolPressed, self.__defaultCallback, self.__defaultCallback,
                 self.__defaultCallback, self.__defaultCallback, self.__defaultCallback,
                 self.__defaultCallback, self.__defaultCallback, self.__defaultCallback,
                 self.__defaultCallback, self.__defaultCallback, self.__defaultCallback,
                 self.__defaultCallback, self.__defaultCallback, self.__defaultCallback,
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
        app.setToolbarButtonDisabled("HELP")
        app.setToolbarButtonDisabled("ABOUT")

        app.startFrame("LEFT", row=0, column=0, rowspan=1, colspan=2)
        app.setBg(conf['manga_bg'])
        app.setSticky("NEWS")
        app.setStretch("BOTH")

        app.addImageData('Manga', self.readImage('./1.png'), fmt='PhotoImage')
        app.stopFrame()

        app.startFrame("RIGHT", row=0, column=2, rowspan=1, colspan=1)

        app.setSticky("NW")
        app.setStretch("COLUMN")
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
        author = "Reiji Miyajima"
        app.addLabel('AuthorL', 'Author:', row=rowCnt, column=0)
        app.addMessage('AuthorMsg', author, row=rowCnt, column=1)
        app.setMessageWidth('AuthorMsg', conf['info_width'])
        rowCnt += 1

        # Chapter
        currChapter = 74
        totalChapter = 74
        app.addLabel('ChapterL', 'Chapter:', row=rowCnt, column=0)
        app.addMessage('ChapterMsg', "%d / %d" %(currChapter, totalChapter), row=rowCnt, column=1)
        app.setMessageWidth('ChapterMsg', conf['info_width'])
        rowCnt += 1

        # State
        isCompleted = False
        app.addLabel('StateL', 'State:', row=rowCnt, column=0)
        app.addMessage('StateMsg', "Completed" if isCompleted else "Ongoing", row=rowCnt, column=1)
        app.setMessageWidth('StateMsg', conf['info_width'])
        rowCnt += 1

        # Last updated
        lastUpdated = 1547130636
        lastUpdatedStr = datetime.utcfromtimestamp(lastUpdated).strftime('%Y-%m-%d %H:%M:%S')
        app.addLabel('LastUpdatedL', 'Last Updated:', row=rowCnt, column=0)
        app.addMessage('LastUpdatedMsg', lastUpdatedStr, row=rowCnt, column=1)
        app.setMessageWidth('LastUpdatedMsg', conf['info_width'])
        rowCnt += 1

        # Label
        labelList = ['Comedy', 'Romance', 'Ecchi', 'School Life', 'Seinen', 'Shounen', 'Mature']
        labelStr = ''
        for l in labelList:
            labelStr += l + ', '
        labelStr = labelStr[:-2]
        app.addLabel('LabelL', 'Labels:', row=rowCnt, column=0)
        app.addMessage('LabelMsg', labelStr, row=rowCnt, column=1)
        app.setMessageWidth('LabelMsg', conf['info_width'])
        rowCnt += 1

        # Intro
        intro = "20-year-old college student Kinoshita Kazuya is feeling gloomy after " \
                "his girlfriend dumped him for another guy. Tired of feeling alone, " \
                "he decides to use the app “Diamond” to get himself a rental girlfriend.\n" \
                "When he meets Mizuhara Chizuru, he thinks he’s finally found the girl of his dreams! " \
                "But is it really possible for things to get intimate between them when Chizuru " \
                "is just a borrowed girlfriend? "
        app.addLabel('IntroL', 'Introduction:', row=rowCnt, column=0)
        app.addMessage('IntroMsg', intro, row=rowCnt, column=1)
        app.setMessageWidth('IntroMsg', conf['info_width'])
        rowCnt += 1

        # Frame ends
        app.stopFrame()
        app.stopFrame()

        # State Bar
        currPage = 2
        updatedAt = 1547130632
        updatedAtStr = datetime.utcfromtimestamp(updatedAt).strftime('%Y-%m-%d %H:%M:%S')

        app.addStatusbar(fields=3)
        app.setStatusbar("Chapter: %d" % currChapter, 0)
        app.setStatusbar("Page: %d" % currPage, 1)
        app.setStatusbar("Updated at: %s" % updatedAtStr, 2)

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


    def loadMangaDir(self):
        self.loadMangaMeta()

    def loadMangaMeta(self):
        with open(os.path.join(self.mangaPath, 'meta.json'), 'r') as f:
            metaObj = json.load(f)

        self.updateNameMsg(metaObj['alias'])

if __name__ == '__main__':
    mv = MangaViewer()
    mv.go()
