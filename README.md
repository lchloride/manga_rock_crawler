# MangaRock Crawler

## Components

- Manga Downloader
- Manga Parser and Converter
- **Manga Viewer**

This document only introduces the Manga Viewer which contains most of features among Downloader and Parser. I think this can satisfy common needs with a GUI panel. 

## Requests

- Python 3
- Requests (for Downloader)
- appJar (for GUI base)
- Pillow (for Images in Viewer)

## Installation

1. Download source code from GitHub.
2. Make sure all needed libraries are in the latest versions.
3. Run the command in the source directory:
   `python gui.py` OR `python3 gui.py`
4. A new window is shown. You can download and view manga here.

## How to use

### 1. Copy the URL of a manga chapter

The URL is similar to this `https://mangarock.com/manga/mrs-serie-61792/chapter/mrs-chapter-61794`. You can find it at chapter list of a manga.
![Chapter list](https://chenghongli.com/image/mangarock1.png)


### 2. Download manga

Run the gui.py, click on the **Download** button. Paste the copied URL and choose the target directory. I recommend to save manga data in an unchanged directory and name it with clear title like "Domestic_Girlfriend_1".

Click **OK** to start downloading. Downloading will take some times depending on the connection stablity. All images of the specific chapter will be download and stored as PNG file. You can watch PNG image in any software you like.

The first page of the chapter will be loaded in viewer automatically when downloading is finished.

### 3. Read manga

Like most of manga viwer, there are a pair of buttons to jump to previous and next pages. Also, there are an another pair of buttons to modify image displaying such as zoom in and out images, move images in four directions. Moreover, some keys are registered for common usage.

![Directions](https://chenghongli.com/image/mangarock2.png)

### 4. Load existed manga

Once the whole chapter of manga is downloaded, you can load it directly without re-downloading. Choose the directory of manga, the content will be loaded automatically.

### 5. Change app language

Currently, English and Simpified Chinese are supported. You can change language at setting panel. By default, English panel is displayed. Besides, the translations only work for fixed words in widgets, which means the contents from MangaRock such as introduction are shown in English.

## More To Do

- Multilanguage support
- Parallel downloading
- Fast loading
- Auto naming
- Custom downloading(download all chapters, automatically fetch URLs, etc.)
- Searching manga by title

## Announcement

The manga and related contents shown in this reference are from Domestic Girlfriend(ドメスティック彼女) by Kei Sasuga(流石景).

Any ideas and suggestions about this application are welcomed. 

## License

This project is under MIT license.



