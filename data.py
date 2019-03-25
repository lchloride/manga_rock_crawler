import sqlite3


class Chapter:
    def __init__(self, iid=None, chapterId=None, seriesId=None, directory=None,
                 createTime=None, updateTime=None, name=None, publish_time=None):
        self._id = iid
        self._chapterId = chapterId
        self._seriesId = seriesId
        self._directory = directory
        self._createTime = createTime
        self._updateTime = updateTime
        self._name = name
        self._publish_time = publish_time

    def getId(self):
        return self._id

    def getChapterId(self):
        return self._chapterId

    def getSeriesId(self):
        return self._seriesId

    def getDirectory(self):
        return self._directory

    def getCreateTime(self):
        return self._createTime

    def getUpdateTime(self):
        return self._updateTime

    def getTuple(self):
        return (self._id, self._chapterId, self._seriesId, self._directory, self._createTime,
                self._updateTime, self._name, self._publish_time)

    def getName(self):
        return self._name

    def getPublishTime(self):
        return self._publish_time

    def setId(self, iid):
        self._id = iid

    def setChapterId(self, chapterId):
        self._chapterId = chapterId

    def setSeriesId(self, seriesId):
        self._seriesId = seriesId

    def setDirectory(self, directory):
        self._directory = directory

    def setCreateTime(self, createTime):
        self._createTime = createTime

    def setUpdateTime(self, updateTime):
        self._updateTime = updateTime

    def setName(self, name):
        self._name = name

    def setPublishTime(self, publish_time):
        self._publish_time = publish_time

    def __str__(self) -> str:
        return 'Chapter(id=%d, chapterId=%d, seriesId=%d, directory=%s, createTime=%d, ' \
               'updateTime=%d, name=%s, publishTime=%d)' \
               % (self._id, self._chapterId, self._seriesId, self._directory, self._createTime,
                  self._updateTime, self._name, self._publish_time)


class Series:
    def __init__(self, iid=None, seriesId=None, updateTime=None, meta=None):
        self._id = iid
        self._seriesId = seriesId
        self._updateTime = updateTime
        self._meta = meta

    def setId(self, iid):
        self._id = iid

    def setSeriesId(self, seriesId):
        self._seriesId = seriesId

    def setUpdateTime(self, updateTime):
        self._updateTime = updateTime

    def setMeta(self, meta):
        self._meta = meta

    def getId(self):
        return self._id

    def getSeriesId(self):
        return self._seriesId

    def getUpdateTime(self):
        return self._updateTime

    def getMeta(self):
        return self._meta

    def getTuple(self):
        return (self._id, self._seriesId, self._updateTime, self._meta)

    def __str__(self) -> str:
        return 'Series(id=%d, seriesId=%d, updateTime=%d, meta=%s)' \
               % (self._id, self._seriesId, self._updateTime, self._meta)


class DataManager:
    def __init__(self, db_name):
        self.conn = sqlite3.connect(db_name)
        self.cursor = self.conn.cursor()
        self.createDatabase()

    def submit(self):
        self.conn.commit()

    def close(self):
        self.conn.close()

    def checkTableExists(self, tableName):
        stmt = '''SELECT name FROM sqlite_master WHERE type='table' AND name=?'''
        self.cursor.execute(stmt, (tableName, ))
        row = self.cursor.fetchone()
        if row is not None and len(row) > 0:
            return True
        else:
            return False

    def createDatabase(self):
        print(self.checkTableExists('chapter'))
        if not self.checkTableExists('chapter'):
            self.createTableChapter()
        if not self.checkTableExists('series'):
            self.createTableSeries()
        self.submit()

    def createTableChapter(self):
        stmt = '''CREATE TABLE "chapter" (
            "id"	INTEGER PRIMARY KEY AUTOINCREMENT,
            "chapterid"	INTEGER UNIQUE,
            "seriesid"	INTEGER NOT NULL,
            "directory"	TEXT,
            "create_time"	INTEGER,
            "update_time"	INTEGER,
            "name"	TEXT NOT NULL,
            "publish_time"	INTEGER NOT NULL
        )'''
        self.cursor.execute(stmt)

    def createTableSeries(self):
        stmt = '''CREATE TABLE `series` (
                `id`	INTEGER PRIMARY KEY AUTOINCREMENT,
                `seriesid`	INTEGER NOT NULL UNIQUE,
                `update_time`	INTEGER NOT NULL,
                `meta`	TEXT NOT NULL
            )'''
        self.cursor.execute(stmt)

    def insertChapter(self, chapter):
        stmt = '''INSERT INTO `chapter`(`chapterid`, `seriesid`, `directory`, `create_time`, `update_time`, `name`, `publish_time`) 
                VALUES (?, ?, ?, ?, ?, ?, ?)'''
        data = chapter.getTuple()[1:]
        self.cursor.execute(stmt, data)
        self.submit()

    def insertSeries(self, series):
        stmt = '''INSERT INTO `series`(`seriesid`, `update_time`, `meta`) VALUES (?, ?, ?)'''
        data = series.getTuple()[1:]
        self.cursor.execute(stmt, data)
        self.submit()

    def selectChapterByChapterId(self, chapterId):
        stmt = '''SELECT * FROM `chapter` WHERE chapterid=?'''
        data = (chapterId,)
        self.cursor.execute(stmt, data)
        row = self.cursor.fetchone()
        if row is None:
            return None
        chapter = Chapter(row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7])
        return chapter

    def selectSeriesBySeriesId(self, seriesId):
        stmt = '''SELECT * FROM `series` WHERE seriesid=?'''
        data = (seriesId,)
        self.cursor.execute(stmt, data)
        row = self.cursor.fetchone()
        if row is None:
            return None
        series = Series(row[0], row[1], row[2], row[3])
        return series

    def updateChapter(self, chapter):
        stmt = '''UPDATE `chapter` SET `directory` = ?, `update_time`= ?, `name`=? WHERE `chapterid`=?'''
        data = (chapter.getDirectory(), chapter.getUpdateTime(), chapter.getName(), chapter.getChapterId())
        self.cursor.execute(stmt, data)
        self.submit()

    def updateSeries(self, series):
        self.updateSeriesMeta(series)

    def updateSeriesMeta(self, series):
        stmt = '''UPDATE `series` SET `meta` = ?, `update_time` = ? WHERE `seriesid` = ?'''
        data = (series.getMeta(), series.getUpdateTime(), series.getSeriesId())
        self.cursor.execute(stmt, data)
        self.submit()


if __name__ == '__main__':
    dm = DataManager('./manga1/data.db')

