from appJar import gui
from PIL import Image, ImageTk
from datetime import datetime


class MangaViewer:
    def __init__(self):
        self.conf = {'width': 900, 'height': 740,
                     'manga_width': 480, 'manga_height': 640,
                     'manga_bg': 'black', 'info_width': 200,
                     }
        self.app = gui("FRAME DEMO", "%dx%d" % (self.conf['width'], self.conf['height']))

        self.__setLayout()

    def readImage(self, filepath):
        conf = self.conf
        oriImg = Image.open(filepath)
        image0 = oriImg.resize((conf['manga_width'], conf['manga_height']), Image.ANTIALIAS)
        img = ImageTk.PhotoImage(image0)
        return img

    def __setLayout(self):
        app = self.app
        conf = self.conf

        app.setBg("yellow")

        tools = ["ABOUT", "REFRESH", "OPEN", "CLOSE", "SAVE",
                 "NEW", "SETTINGS", "PRINT", "SEARCH", "UNDO",
                 "REDO", "PREFERENCES", "HOME", "HELP", "CALENDAR",
                 "WEB", "OFF"]

        app.addToolbar(tools, self.__defaultCallback, findIcon=True)

        app.startFrame("LEFT", row=0, column=0, rowspan=1, colspan=2)
        app.setBg(conf['manga_bg'])
        app.setSticky("NEW")
        app.setStretch("COLUMN")

        app.addImageData('Manga', self.readImage('./ch100399152_3.png'), fmt='PhotoImage')
        app.stopFrame()

        app.startFrame("RIGHT", row=0, column=2, rowspan=1, colspan=1)

        app.setSticky("NW")
        app.setStretch("COLUMN")
        app.startFrame('RR', row=0, column=1)
        app.setSticky("NW")
        app.setPadX(5)
        app.setFont(12)

        app.addLabel('InfoL', 'Information')
        app.getLabelWidget("InfoL").config(font=("Comic Sans", "14", "bold"))

        # Name list
        aliasList = ["Kanojo, Okarishimasu", "I'd like to Borrow a Girlfriend", "여친, 빌리겠습니다",
                 "彼女、お借りします", "女朋友、借我一下"]
        app.addLabel('NameL', 'Name:', row=1, column=0)
        for i, alias in enumerate(aliasList):
            nameId = 'NameMsg'+str(i)
            app.addMessage(nameId, alias, row=1+i, column=1)
            app.setMessageWidth(nameId, conf['info_width'])
        rowCnt = 1 + len(aliasList)

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

        app.addStatusbar(fields=3)
        app.setStatusbar("Line: 20", 0)
        app.setStatusbar("Column: 4", 1)
        app.setStatusbar("Mode: Edit", 2)

    def __defaultCallback(self, name):
        print(name)

    def go(self):
        self.app.go()

if __name__ == '__main__':
    mv = MangaViewer()
    mv.go()
