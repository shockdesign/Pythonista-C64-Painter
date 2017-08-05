#!python2


# Pythonista C64 Painter AKA Redux Paint
#
# Personal project for learning Python
# Bring holy handgrenades, here be monstrous code and vicious rabbits!
#
# Scripted by Rune Spaans
# Based on the Pythonista Pixel Editor by Sebastian Jarsve
#
#
# Features Todo:
# - Icons change state when pressed
# - Clash test tool icon
# - Brush sizes
# - Koala Paint export
# - Only draw on bg color mode (like Manga Paint background mode)
# - Flip image vertically and horizontally
# - Pan image with arrow keys
# - Pan tool
# - Palm reject
# - Add CRT-effect to preview
# - New undo-system; Hold a number of stroke undos, not per-pixel history.
# - Make colour set to BG draw as transparent?
# - Select an area, flip, rotate and move contents around.
#
#
# Fixes/Bugs Todo:
#
# - Zoom function sometimes ends by drawing a pixel, figure out why
# - Activity indicator will not appear, figure out why
# - Error on exit if there is no image. has_image function fails
# - Code changes have resulted in multiple duplicate functions, go through and clean up
# - Optimize draw line
# - Optimize redraw screen

import console
import scene
import photos
import clipboard
import ui
import Image
#import ImageFilter

from io import BytesIO
from os.path import isfile
from time import time, sleep
from datetime import datetime
#from ImageOps import invert


# Settings used across the editor
class Settings (object):
    undoSteps = 10
    autoSaveTime = 30 # Number of seconds between autosaves
    previewTime = 2 # Seconds to wait between preview 
    width = 320
    height = 200
    pixelSize = 2 # 1: C64 singlecolor mode, 2: C64 multicolor mode
    actualWidth = width / pixelSize
    charSize = 8
    c64color_palette = [ (0, 0, 0), (252, 252, 252), (141, 58, 76), (131, 192, 176), (147, 73, 161), (97, 167, 95), (63, 56, 172), (207, 215, 109), (146, 91, 38), (99, 65, 8), (190, 110, 129), (85, 85, 85), (130, 130, 130), (165, 228, 152), (128, 118, 229), (169, 169, 169) ] # Grabbed from Youtube video of a real C64
    #c64color_palette = [ (0, 0, 0), (255, 255, 255), (158, 59, 80), (133, 233, 209), (163, 70, 182), (93, 195, 94), (61, 51, 191), (249, 255, 126), (163, 98, 33), (103, 68, 0), (221, 121, 138), (86, 89, 86), (138, 140, 137), (182, 253, 184), (140, 128, 255), (195, 195, 193) ] # My original DV capture palette
    c64color_labels = [ "black", "white", "red", "cyan", "purple", "green", "blue", "yellow", "orange", "brown", "pink", "darkgrey", "grey", "lightgreen", "lightblue", "lightgrey"]


# Convert colors from [0,255] to [0,1]
def color_to_1(color):
    if len(color) == 4:
        return (color[0]/255.0, color[1]/255.0, color[2]/255.0, color[3]/255.0)
    elif len(color) == 3:
        return (color[0]/255.0, color[1]/255.0, color[2]/255.0, 1.0)
    else:
        print ("Color data seems wrong: " + str(color))
        return (1, 0, 0, 1) # Red


def color_to_255(color):
    return (int(color[0]*255), int(color[1]*255), int(color[2]*255))


# Returns the closest to given color in the C64-palette
def closest_in_palette(matchColor,matchPalette):
    i = 0
    bestDelta = 1000
    c = 0
    for color in matchPalette:
        r = sorted((color[0],matchColor[0]))
        g = sorted((color[1],matchColor[1]))
        b = sorted((color[2],matchColor[2]))
        delta = r[1]-r[0] + g[1]-g[0] + b[1]-b[0]
        if delta < bestDelta:
            i = c
            bestDelta = delta
        c = c + 1
    return matchPalette[i]


# Check if number is even or odd, used by checkered paint mode
def is_odd(x):
    return (x % 2)


def xy_to_index(xcoord,ycoord):
    arrayIndex = (ycoord*Settings.actualWidth) + xcoord
    return arrayIndex


def index_to_xy(arrayIndex):
    ycoord = int(arrayIndex/Settings.actualWidth)
    xcoord = arrayIndex - (Settings.actualWidth * ycoord)
    return (xcoord,ycoord)


def pil_to_ui(img):
    with BytesIO() as bIO:
        img.save(bIO, 'png')
        return ui.Image.from_data(bIO.getvalue())


# Convert from ui.image to PIL Image
def ui_to_pil(img):
    return Image.open(BytesIO(img.to_png()))


def pixels_to_png(bg_color, pixels, width, height, filename):
    # Create image
    bgColor = color_to_255(bg_color)
    im = Image.new("RGB", (width, height), bgColor)
    # Fill with pixels
    for p in pixels:
        pixelCol = bgColor
        if p.color[3] != 0:
            # convert pixel data from RGBA 0..1 to RGB 0..255
            pixelCol = color_to_255(p.color)
            im.putpixel((int(p.position[0]*2),p.position[1]),pixelCol)
            im.putpixel((int(p.position[0]*2)+1,p.position[1]),pixelCol)
    im.save(filename)
    return True


def file_to_img(width, height, filename):
    # Do a check for file type
    im = Image.open(filename).convert('RGBA')
    im = im.resize((Settings.actualWidth, Settings.height), Image.NEAREST)
    return im


# Takes index as an input at returns all indices for a character
def get_char(index):
    charArray = []
    ## Coming soon!
    #
    # 
    return charArray


# The Pixel, an array of these holds the current image
class Pixel (object):
    def __init__(self, x, y, w, h):
        self.rect = scene.Rect(x, y, w, h)  # Important: (x,y) is the lower-left corner
        self.color = (0, 0, 0, 0)
        self.index = 0                      # Used to find neighbors
        self.position = (x,y)               # Used when writing images


# The undo stack, keeps all data for undoing strokes        
class UndoStack (object):
    undoData = []
    
    def clearStack():
        undoData = []
        return True


class PixelEditor(ui.View):
    # 1: 1x1 pixel, 2: 1x2 pixels, 3: 2x4 pixels, 4: character (4x8 pixels)
    brushSize = 1
    previewMode = 1 # 0: off, 1:normal size, 2: double size
    toolMode = 'dots'
    prevMode = 'dots'
    drawDithered = False
    gridOpacity = 0.5
    darkGrid = False
    prevPixel = []
    imageName = ""

    # The various zoom levels
    zoomLevels = (2, 3, 6, 9)
    zoomCurrent = 1 # What level we're currently zooming to
    zoomState = False

    # Last autosave and undo time
    lastSave = 0
    lastUndo = 0

    def did_load(self):
        self.row = Settings.width/Settings.pixelSize
        self.column = Settings.height
        self.lastSave = int(time())
        self.pixels = []
        self.image_view = self.create_image_view()
        self.grid_layout = self.create_grid_layout()
        self.color_check = self.create_image_view()
        self.color_check.hidden = True
        self.image_view.image = self.create_new_image() # Needs to be set twice for some reason..
        self.zoom_frame = self.create_zoom_frame()
        self.grid_layout.alpha = self.gridOpacity
        self.current_color = (1, 1, 1, 1)
        ## Todo: Loading auto-save should probably be here.
        ## But it does not work, probably because the preview 
        ## view hasn't been created yet?
        #if isfile("images/_tempsave.png"):
        #    self.loadimage("images/_tempsave.png")
        
        
    def checkDither(self, position):
        if self.drawDithered == False: return True
        if is_odd(position[0]) and is_odd(position[1]) or is_odd(position[0]+1) and is_odd(position[1]+1):
            return False
        else: return True

    # Check if image is not all black
    def has_image(self):
        im = ui_to_pil(self.image_view.image)
        extrema = im.convert("L").getextrema()
        if extrema == (0, 0):
            # all black
            return False
        else:
            return True

    def create_zoom_frame(self):
        zoomWidth = self.width / self.zoomLevels[self.zoomCurrent]
        zoomHeight = self.height / self.zoomLevels[self.zoomCurrent]
        # create an movable image showing the zoom area
        with ui.ImageContext(320,200) as ctx:
            ui.set_color('black')
            line_inside = ui.Path.rect(2,2,316,196)
            line_inside.line_width = 4
            line_inside.stroke()
            ui.set_color('white')
            line_outside = ui.Path.rect(0,0,320,200)
            line_outside.line_width = 4
            line_outside.stroke()
            zoomSquare = ctx.get_image()
        zoom_frame = ui.ImageView(hidden=True)
        zoom_frame.bounds = (0,0,zoomWidth,zoomHeight)
        zoom_frame.center = (self.width/2, self.height/2)
        zoom_frame.image = zoomSquare
        self.add_subview(zoom_frame)
        return zoom_frame

    def get_zoom_center(self):
        return (self.superview['editor'].zoom_frame.center)

    def set_zoom_center(self, position):
        borderWidth = self.superview['editor'].width / self.zoomLevels[self.zoomCurrent] * 0.5
        borderHeight = self.superview['editor'].height / self.zoomLevels[self.zoomCurrent] * 0.5
        xPos = min(max(borderWidth, position[0]), self.superview['editor'].width-borderWidth)
        yPos = min(max(borderHeight, position[1]), self.superview['editor'].height-borderHeight)
        self.superview['editor'].zoom_frame.center = (xPos, yPos)
        return (xPos, yPos)

    def set_zoom_size(self):
        zoomWidth = self.width / self.zoomLevels[self.zoomCurrent]
        zoomHeight = self.height / self.zoomLevels[self.zoomCurrent]
        self.superview['editor'].zoom_frame.width = zoomWidth
        self.superview['editor'].zoom_frame.height = zoomHeight

    def get_zoom_region(self):
        zoomCenter = self.zoom_frame.center
        halfWidth = 319 * 0.5 / self.zoomLevels[self.zoomCurrent]
        halfHeight = 199 * 0.5 / self.zoomLevels[self.zoomCurrent]
        zoomFrom = (int((zoomCenter[0]/3-halfWidth)*0.5), int(zoomCenter[1]/3-halfHeight))
        zoomTo = (int((zoomCenter[0]/3+halfWidth)*0.5), int(zoomCenter[1]/3+halfHeight))
        return(zoomFrom,zoomTo)
    
    # Returns the currently displayed region, 0-based    
    def get_current_region(self):
        return (self.get_zoom_region()) if (self.zoomState == True) else ( (0, 0) , ((Settings.width/Settings.pixelSize)-1, Settings.height-1) )
    
    def set_image(self, image=None):
        # Image is set to provided image or a new is created
        image = image or self.create_new_image()
        self.image_view.image = image
        
    def get_image(self):
        image = self.image_view.image
        return image

    # Initializes the image, draws the pixel array, image and grid lines
    def init_pixel_grid(self):
        s = self.width/self.row if self.row > self.column else self.height/self.column
        path = ui.Path.rect(0, 0, *self.frame[2:])
        charpath = ui.Path.rect(0, 0, *self.frame[2:])
        with ui.ImageContext(*self.frame[2:]) as ctx:
            # Fills entire grid with empty color
            ui.set_color((0, 0, 0, 0))
            path.fill()
            # Grid line per pixel
            path.line_width = 1
            for y in xrange(self.column):
                for x in xrange(self.row):
                    # Fills image with pixels
                    # Changing this changes the pixel aspect
                    pixel = Pixel(x*s*2, y*s, s*2, s)
                    pixel.index = len(self.pixels)
                    pixel.position = (x,y)
                    path.append_path(ui.Path.rect(*pixel.rect))
                    self.pixels.append(pixel) #Adds this pixel to the pixels list
            ui.set_color((0.5,0.5,0.5,0.5))
            path.stroke()
            # Grid line per character
            for y in xrange(self.column/8):
                for x in xrange(self.row/4):
                    #pixel = Pixel(x*s*8, y*s*8, s*8, s*8)
                    #charpath.append_path(ui.Path.rect(*pixel.rect))
                    charpath.append_path(ui.Path.rect(x*s*8, y*s*8, s*8, s*8))
            ui.set_color((1,1,1,0.5))
            charpath.stroke()
            return ctx.get_image()
    
    def create_new_image(self):
        path = ui.Path.rect(*self.bounds)
        with ui.ImageContext(self.width, self.height) as ctx:
            ui.set_color((0, 0, 0, 0))
            path.fill()
            return ctx.get_image()

    def create_grid_layout(self):
        image_view = ui.ImageView(frame=self.bounds)
        image_view.image = self.init_pixel_grid()
        self.add_subview(image_view)
        return image_view

    def create_image_view(self):
        image_view = ui.ImageView(frame=self.bounds)
        image_view.image = self.create_new_image()
        self.add_subview(image_view)
        return image_view

    def position_pixels(self):
        # Upper right and lower left corner of pixels in the view
        (startPos, endPos) = self.get_current_region()
        pixelScale = self.width / (endPos[0]-startPos[0]+1) / Settings.pixelSize # Pixel scale
        viewPixels = []     # Array holding the pixels in the view
        # Move all pixels off-screen
        if self.zoomState == True:
            for index in xrange(0,len(self.pixels)):
                self.pixels[index].rect.x = self.pixels[index].rect.y = -100
        # Position zoomed pixels over canvas
        for y in xrange(startPos[1],endPos[1]+1):
            for x in xrange(startPos[0],endPos[0]+1):
                curPixel = self.pixels[xy_to_index(x,y)]
                viewPixels.append(curPixel.index)
                # rect.x, rect.y is components LOWER-left corner
                curPixel.rect.x = (x-startPos[0]) * pixelScale * Settings.pixelSize
                curPixel.rect.y = (y-startPos[1]) * pixelScale
                curPixel.rect.width = pixelScale * Settings.pixelSize
                curPixel.rect.height = pixelScale
        return viewPixels
    
    def draw_grid_image(self):
        (startPos, endPos) = self.get_current_region()
        charSize = Settings.charSize
        pixelScale =  self.width/(endPos[0]-startPos[0]+1)/Settings.pixelSize #self.height/Settings.height
        #s = self.width/self.row if self.row > self.column else self.height/self.column
        pixelGrid = ui.Path.rect(0, 0, *self.frame[2:])
        characterGrid = ui.Path.rect(0, 0, *self.frame[2:])
        with ui.ImageContext(*self.frame[2:]) as ctx:
            # Fills entire grid with empty color
            ui.set_color((0, 0, 0, 0))
            pixelGrid.fill()
            pixelGrid.line_width = 1
            # Grid line per pixel
            for y in xrange(startPos[1], endPos[1]+1):
                for x in xrange(startPos[0], endPos[0]+1):
                    pixelGrid.append_path(ui.Path.rect((x-startPos[0])*pixelScale*2, (y-startPos[1])*pixelScale, pixelScale*2, pixelScale))
            drawColor = (0.5,0.5,0.5,0.5) if self.darkGrid == False else (0.25,0.25,0.25,0.5)
            ui.set_color(drawColor)
            pixelGrid.stroke()
            # Grid line per character
            for y in xrange(int(startPos[1]/charSize)*charSize, endPos[1]+1, charSize):
                for x in xrange(int(startPos[0]/charSize*charSize), endPos[0]+1,4):
                    characterGrid.append_path(ui.Path.rect((x-startPos[0])*pixelScale*2, (y-startPos[1])*pixelScale, pixelScale*charSize, pixelScale*charSize))
            drawColor = (1,1,1,0.5) if self.darkGrid == False else (0,0,0,0.5)
            ui.set_color(drawColor)
            characterGrid.stroke()
            return ctx.get_image()    
                
    # Redraws the main editor window
    def redraw_canvas(self):
        # Gets the pixels covered by the current zoom level
        zoomPixels = self.position_pixels()
        # Redraw view
        self.image_view.image = self.create_new_image()
        with ui.ImageContext(self.width, self.height) as ctx:
            for i in zoomPixels:
                p = self.pixels[i]
                ui.set_color(p.color)
                pixel_path = ui.Path.rect(p.rect[0],p.rect[1],p.rect[2],p.rect[3])
                pixel_path.line_width = 0.5
                pixel_path.fill()
                pixel_path.stroke()
            self.image_view.image = ctx.get_image()
            ## Todo: insert drawing of preview window:
        # Redraw grid
        self.grid_layout.image = self.draw_grid_image()
        self.grid_layout.alpha = self.gridOpacity
        return True
    
    # Check characters if they have a legal amount of colours
    def character_colorcheck_old(self):
        #self.color_check.hidden = False
        debugCount = 0
        with ui.ImageContext(self.width, self.height) as ctx:
            for row in range (0, 25):
                for col in range (0, 40):
                    # Collect pixels in current character
                    charColors ={(self.background_color[0], self.background_color[1], self.background_color[2])}
                    startIndex = col*4 + row*Settings.actualWidth*Settings.charSize
                    for pixelRow in range(0, 8):
                        for pixelCol in range (0, 4):
                            pixelIndex = startIndex + pixelRow*Settings.actualWidth + pixelCol
                            charColors.add((self.pixels[pixelIndex].color[0], self.pixels[pixelIndex].color[1], self.pixels[pixelIndex].color[2]))
                    if len(charColors) > 4:
                        p = self.pixels[startIndex]
                        ui.set_color('red')
                        pixel_path = ui.Path.rect(p.rect[0],p.rect[1],p.rect[2]*Settings.charSize*0.5,p.rect[3]*Settings.charSize)
                        pixel_path.line_width = 2
                        #pixel_path.fill()
                        pixel_path.stroke()
                        self.color_check.image = ctx.get_image()
                        if debugCount < 40: 
                            print (str(len(charColors)) + " colors at character " + str(col) + "," + str(row) )
                            #print str(charColors)
                        debugCount = debugCount + 1
    
    def character_colorcheck(self):
        (startPos, endPos) = self.get_current_region()
        charSize = Settings.charSize
        pixelScale =  self.width/(endPos[0]-startPos[0]+1)/Settings.pixelSize #self.height/Settings.height
        #s = self.width/self.row if self.row > self.column else self.height/self.column
        with ui.ImageContext(self.width, self.height) as ctx:
            ui.set_color('red')
            # Grid line per character
            for y in xrange(int(startPos[1]/charSize)*charSize, endPos[1]+1, charSize):
                for x in xrange(int(startPos[0]/charSize*charSize), endPos[0]+1,4):
                    # Check this character for color clash
                    charColors ={(self.background_color[0], self.background_color[1], self.background_color[2])}
                    startIndex = xy_to_index(x,y)
                    for pixelRow in range(0, 8):
                        for pixelCol in range (0, 4):
                            pixelIndex = startIndex + pixelRow*Settings.actualWidth + pixelCol
                            charColors.add((self.pixels[pixelIndex].color[0], self.pixels[pixelIndex].color[1], self.pixels[pixelIndex].color[2]))
                    if len(charColors) > 4:
                        pixel_path = ui.Path.rect((x-startPos[0])*pixelScale*2, (y-startPos[1])*pixelScale, pixelScale*charSize, pixelScale*charSize)
                        pixel_path.line_width = 2
                        pixel_path.stroke()
                        self.color_check.image = ctx.get_image()    
    
    #@ui.in_background
    def preview_init(self):
        path = ui.Path.rect(0, 0, Settings.width, Settings.height)
        with ui.ImageContext(Settings.width, Settings.height) as ctx:
            ui.set_color((0, 0, 0, 1))
            path.fill()
            self.superview['preview'].image = ctx.get_image()
        return True
    
    @ui.in_background
    def preview_putimg(self, ui_img):
        pil_img = ui_to_pil(ui_img)
        pil_img = pil_img.resize((Settings.width, Settings.height), Image.NEAREST)
        self.superview['preview'].image = pil_to_ui(pil_img)
        return True

    @ui.in_background            
    def preview_drawPixels(self):
        zoomPixels = self.position_pixels()
        old_img = self.superview['preview'].image
        with ui.ImageContext(Settings.width, Settings.height) as ctx:
            old_img.draw()
            for i in zoomPixels:
                p = self.pixels[i]
                ui.set_color(p.color)
                pixel_path = ui.Path.rect(p.position[0]*Settings.pixelSize,p.position[1],1*Settings.pixelSize,1)
                pixel_path.line_width = 0.5
                pixel_path.fill()
                pixel_path.stroke()
            self.superview['preview'].image = ctx.get_image()
            
    def preview_update(self):
        if self.zoomState == False:
            self.preview_putimg(self.image_view.image)
        else:
            self.preview_drawPixels()
        
    def reset(self, row=None, column=None):
        self.pixels = []
        self.grid_layout.image = self.init_pixel_grid()
        self.set_image()
    
    def fastsave(self, file_name=""):
        if self.has_image():
            file_name = "images/" + file_name + ".png"
            print('Saving temp image ' + file_name)
            pixels_to_png(self.background_color, self.pixels, Settings.width, Settings.height, file_name)
            print('Saved!')
            return True
        #else:
        #    print("Attempted autosave with no image data.")

    #@ui.in_background
    def loadimage(self, file_name, colorcheck=True):
        self.color_check.hidden = True
        loadImg = file_to_img(Settings.height, Settings.width, file_name)
        img = self.create_new_image()
        charRowSize = Settings.actualWidth * Settings.charSize
        # We read and draw the image one character line at a time
        #indicator = ui.ActivityIndicator()
        #indicator.center = self.center
        #self.add_subview(indicator)
        #indicator.bring_to_front()
        #indicator.start()
        for charRow in xrange(0, Settings.height/Settings.charSize):
            indexArray = []
            startIndex = charRow*charRowSize
            endIndex = charRow*charRowSize + charRowSize
            #print ("Importing subrow: " + str(startIndex) + ", " + str(endIndex))
            for i in xrange(startIndex, endIndex):
                indexArray.append(i)
                pixelCol = loadImg.getpixel(self.pixels[i].position)
                # Find the closest color in the C64 palette
                if colorcheck == True:
                    pixelCol = closest_in_palette(pixelCol,Settings.c64color_palette)
                self.pixels[i].color = color_to_1(pixelCol)
            img = self.draw_index_array(img, indexArray)
            self.set_image(img)
        self.preview_putimg(img)
        #indicator.stop()
        #self.remove_subview(indicator)
        return True
        
    def pencil(self, pixel):
        if pixel.color != self.current_color:
            pixel.color = self.current_color
            #self.pixel_path.append(pixel)
            old_img = self.image_view.image
            path = ui.Path.rect(*pixel.rect)
            with ui.ImageContext(self.width, self.height) as ctx:
                if old_img:
                    old_img.draw()
                ui.set_color(self.current_color)
                pixel_path = ui.Path.rect(*pixel.rect)
                pixel_path.line_width = 0.5
                pixel_path.fill()
                pixel_path.stroke()
                self.set_image(ctx.get_image())

    def drawline(self, prevPixel, pixel, touchState):
        doLine = False
        xDist = 0
        yDist = 0
        if self.prevPixel != []:
            # Only draw lines inside or at the end of touch
            if touchState == "moved" or touchState == "ended":
                # Check if distance is more than 1 pixel on either axis
                xDist = max(pixel.position[0], self.prevPixel.position[0]) - min(pixel.position[0], self.prevPixel.position[0])
                yDist = max(pixel.position[1], self.prevPixel.position[1]) - min(pixel.position[1], self.prevPixel.position[1])
                #print ("x:" + str(xDist) + ", y:" + str(yDist))
                if xDist > 1 or yDist > 1:
                    doLine = True
        if doLine != True:
            # Line segment is too short, a single pixel is sufficient
            #self.current_color = 'white' # debug color
            self.drawpixel(pixel)
        else:
            #self.current_color = 'red' # debug color
            self.drawpixel(prevPixel)
            self.drawpixel(pixel)
            curPixel = None
            linePixels = []
            xStart = prevPixel.position[0]
            yStart = prevPixel.position[1]
            xDir = 1 if xStart < pixel.position[0] else -1
            yDir = 1 if yStart < pixel.position[1] else -1
            yIncr = 0 if yDist == 0 else (float(xDist)/yDist)
            xIncr = 0 if xDist == 0 else (float(yDist)/xDist)
            # Update all pixel objects along the drawn line
            for c in xrange(1, max(xDist,yDist)):
                if yDist >= xDist:
                    #self.current_color = 'yellow' # debug color
                    curPixel = self.pixels[ xy_to_index( int(xStart+(yIncr*c*xDir)+0.5), int(yStart+(c*yDir)) ) ]
                else:
                    #self.current_color = 'purple' # debug color
                    curPixel = self.pixels[ xy_to_index( xStart+(xDir*c), int(yStart+(xIncr*c*yDir)) ) ]
                if curPixel.color != self.current_color and self.checkDither(curPixel.position):
                    curPixel.color = self.current_color
                    linePixels.append(curPixel)
            # Redraw the image
            old_img = self.image_view.image
            with ui.ImageContext(self.width, self.height) as ctx:
                if old_img:
                    old_img.draw()
                for curPixel in linePixels:
                    path = ui.Path.rect(*curPixel.rect)
                    ui.set_color(self.current_color)
                    pixel_path = ui.Path.rect(*curPixel.rect)
                    pixel_path.line_width = 0.5
                    pixel_path.fill()
                    pixel_path.stroke()
                self.set_image(ctx.get_image())

        self.prevPixel = pixel
        return True

    def drawpixel(self, pixel):
        if pixel.color != self.current_color:
                #if self.drawDithered == False or (is_odd(pixel.position[0]) and is_odd(pixel.position[1]) or is_odd(pixel.position[0]+1) and is_odd(pixel.position[1]+1)):
            if self.checkDither(pixel.position):
                pixel.color = self.current_color
                #self.pixel_path.append(pixel)
                old_img = self.image_view.image
                path = ui.Path.rect(*pixel.rect)
                with ui.ImageContext(self.width, self.height) as ctx:
                    if old_img:
                        old_img.draw()
                    ui.set_color(self.current_color)
                    pixel_path = ui.Path.rect(*pixel.rect)
                    pixel_path.line_width = 0.5
                    pixel_path.fill()
                    pixel_path.stroke()
                    self.set_image(ctx.get_image())

    # Draw pixels from array on top of image (ui.image)
    def draw_index_array(self, img, indexArray):
        with ui.ImageContext(self.width, self.height) as ctx:
            img.draw()
            for i in indexArray:
                p = self.pixels[i]
                path = ui.Path.rect(*self.pixels[i].rect)
                ui.set_color(p.color)
                pixel_path = ui.Path.rect(p.rect[0],p.rect[1],p.rect[2],p.rect[3])
                pixel_path.line_width = 0.5
                pixel_path.fill()
                pixel_path.stroke()
            img = ctx.get_image()
        return img

    def action(self, touch, touchState):
        p = scene.Point(*touch.location)
        for pixel in self.pixels:
            if p in pixel.rect:
                # Auto-save image
                saveDelta = int(time()) - self.lastSave
                if saveDelta > Settings.autoSaveTime:
                    self.superview['debugtext'].text = "Autosaving..."
                    currentTime = str(datetime.now().day) + "_" + str(datetime.now().hour)
                    self.fastsave(self.imageName + "_worksave_" + currentTime)
                    self.lastSave = int(time())
                if self.toolMode == 'dots':
                    self.drawpixel(pixel)
                    if self.toolMode == 'lines' or self.toolMode == 'dots':
                        self.superview['debugtext'].text = "index:" + str(pixel.index) + ", pos:" + str(pixel.position) + ", autosave:" + str(Settings.autoSaveTime-saveDelta)
                elif self.toolMode == 'lines':
                    if touchState == 'began':
                        self.prevPixel == []
                    self.drawline(self.prevPixel, pixel, touchState)
                    self.prevPixel = pixel
                    if touchState == "ended":
                        #self.preview_update()
                        self.prevPixel = []
                    if self.toolMode == 'lines' or self.toolMode == 'dots':
                        self.superview['debugtext'].text = "index:" + str(pixel.index) + ", pos:" + str(pixel.position) + ", autosave:" + str(Settings.autoSaveTime-saveDelta)
                elif self.toolMode == 'zoom':
                    self.set_zoom_center(touch.location)

                    # Calculate the bounds of the zoom area
                    zoomCenter = self.zoom_frame.center
                    halfWidth = 319 * 0.5 / self.zoomLevels[self.zoomCurrent]
                    halfHeight = 199 * 0.5 / self.zoomLevels[self.zoomCurrent]
                    zoomFrom = (int((zoomCenter[0]/3-halfWidth)*0.5), int(zoomCenter[1]/3-halfHeight))
                    zoomTo = (int((zoomCenter[0]/3+halfWidth)*0.5), int(zoomCenter[1]/3+halfHeight))

                    # Debug text for zoom mode
                    self.superview['debugtext'].text = "Zoom location: [" + str(zoomFrom) + "," + str(zoomTo) + "], zoom level:" + str(self.zoomLevels[self.zoomCurrent])

                    # When the finger is released, we draw the zoomed view
                    if touchState == "ended":
                        self.superview['debugtext'].text = "Zooming in"
                        self.zoomState = True
                        self.redraw_canvas()
                        self.zoom_frame.hidden = True
                        if self.color_check.hidden == False:
                            self.character_colorcheck()

                        # Return to previous tool mode
                        self.toolMode = self.prevMode
                        self.superview['debugtext'].text = "Mode set back to " + self.toolMode
                        ## Todo: Sometimes, random dots get drawn after this command
                        ## Investigate why
                # Update preview image
                undoDelta = int(time()) - self.lastUndo
                if undoDelta > Settings.previewTime:
                    self.preview_update()
                    self.lastUndo = int(time())
                

    def touch_began(self, touch):
        self.action(touch, "began")

    def touch_moved(self, touch):
        self.action(touch, "moved")

    def touch_ended(self, touch):
        self.action(touch, "ended")


class ColorView (ui.View):
    c64color_gradient = [0, 6, 9, 2, 11, 4, 8, 14, 12, 5, 10, 3, 15, 7, 13, 1]

    c64hex = ["00", "01", "02", "03", "04", "05", "06", "07", "08", "09", "0A", "0B", "0C", "0D", "0E", "0F"]

    palette_type = 'numeric'

    def did_load(self):
        self.color = {'r':0, 'g':0, 'b':0, 'a':1}
        for subview in self.subviews:
            self.init_action(subview)
        self.set_palette(self.palette_type)

    def init_action(self, subview):
        if hasattr(subview, 'action'):
            subview.action = self.choose_color if subview.name != 'clear' else self.clear_user_palette
        if subview.name == 'set_palette':
            subview.action = self.set_palette
        if hasattr(subview, 'subviews'):
            for sv in subview.subviews:
                self.init_action(sv)

    def palette_list(self):
        for subview in self['palette'].subviews:
            print (subview.title + ": (" + str(int(subview.background_color[0]*255)) + ", " + str(int(subview.background_color[1]*255)) + ", " + str(int(subview.background_color[2]*255)) + ")")

    def set_palette(self, sender):
        num = 0
        if self.palette_type == 'numeric':
            for subview in self['palette'].subviews:
                subview.background_color = color_to_1(Settings.c64color_palette[num])
                subview.title = self.c64hex[num]
                num = num + 1
            self.palette_type = "gradient"
            self.subviews[3].title = "0-F"
            try:
                self.superview['debugtext'].text = "Palette set to numeric"
            except Exception:
                pass
        elif self.palette_type == 'gradient':
            for subview in self['palette'].subviews:
                subview.background_color = color_to_1(Settings.c64color_palette[self.c64color_gradient[num]])
                subview.title = self.c64hex[self.c64color_gradient[num]]
                num = num + 1
            self.palette_type = "numeric"
            self.subviews[3].title = "grad"
            self.superview['debugtext'].text = "Palette set to gradient"

    def get_color(self):
        return tuple(self.color[i] for i in 'rgba')

    def set_color(self, color=None):
        color = color or self.get_color()
        if self['current_color'].background_color == color:
            # Set color twice, and the image bg color will be set
            self['bg_color'].background_color = color
            self.superview['editor'].background_color = color
            if self.superview['editor'].color_check.hidden == False:
                self.superview['editor'].character_colorcheck()
        else:
            self['current_color'].background_color = color
            self.superview['editor'].current_color = color
            self.superview['debugtext'].text = "BG color set to " + str(color_to_255(color))
            
    @ui.in_background
    def choose_color(self, sender):
        if sender.name in self.color:
            self.color[sender.name] = sender.value
            self.set_color()
        elif sender in self['palette'].subviews:
            self.set_color(sender.background_color)
        elif sender.name == 'color_input':
            try:
                c = sender.text if sender.text.startswith('#') else eval(sender.text)
                v = ui.View(background_color=c)
                self['color_input'].text = str(v.background_color)
                self.set_color(v.background_color)
            except Exception as e:
                console.hud_alert('Invalid Color', 'error')

class ToolbarView (ui.View):
    # Customize view after loading UI file
    def did_load(self):
        ## Todo: This seems like a very inelegant solution for changing button images
        self.subviews[0].subviews[0].title = ""
        self.subviews[0].subviews[0].background_image = ui.Image.named('icons/tool_dots_64.png')
        self.subviews[0].subviews[1].title = ""
        self.subviews[0].subviews[1].background_image = ui.Image.named('icons/tool_undo_64.png')
        self.subviews[0].subviews[2].title = ""
        self.subviews[0].subviews[2].background_image = ui.Image.named('icons/tool_clear_64.png')
        self.subviews[0].subviews[3].title = ""
        self.subviews[0].subviews[3].background_image = ui.Image.named('icons/tool_save_64.png')
        self.subviews[0].subviews[4].title = ""
        self.subviews[0].subviews[4].background_image = ui.Image.named('icons/tool_preview_64.png')
        self.subviews[0].subviews[5].title = ""
        self.subviews[0].subviews[5].background_image = ui.Image.named('icons/tool_zoom_64.png')
        self.subviews[0].subviews[6].title = ""
        self.subviews[0].subviews[6].background_image = ui.Image.named('icons/tool_load_64.png')
        self.subviews[0].subviews[7].title = ""
        self.subviews[0].subviews[7].background_image = ui.Image.named('icons/tool_grid_64.png')
        self.subviews[0].subviews[8].title = ""
        self.subviews[0].subviews[8].background_image = ui.Image.named('icons/tool_lines_64.png')
        self.subviews[0].subviews[9].title = ""
        self.subviews[0].subviews[9].background_image = ui.Image.named('icons/tool_exit_64.png')
        self.subviews[0].subviews[10].title = ""
        self.subviews[0].subviews[10].background_image = ui.Image.named('icons/tool_zoomlevel_64.png')
        self.subviews[0].subviews[11].title = ""
        self.subviews[0].subviews[11].background_image = ui.Image.named('icons/tool_dither_64.png')
        self.subviews[0].subviews[0].image = None
        #pass
        #self.pixel_editor = self.superview['editor']
        #for subview in self.subviews:
        #   self.init_actions(subview)

    def init_actions(self, subview):
        if hasattr(subview, 'action'):
            if hasattr(self, subview.name):
                subview.action = eval('self.{}'.format(subview.name))
            #else:
            #  subview.action = self.set_mode
        if hasattr(subview, 'subviews'):
            for sv in subview.subviews:
                self.init_actions(sv)

    def show_error(self):
        console.hud_alert('Editor has no image', 'error', 0.8)

    def paintdots(self, sender):
        self.superview['editor'].toolMode = 'dots'
        self.superview['editor'].zoom_frame.hidden = True
        self.superview['debugtext'].text = "Painting dots!"

    def paintlines(self, sender):
        self.superview['editor'].toolMode = 'lines'
        self.superview['editor'].zoom_frame.hidden = True
        self.superview['debugtext'].text = "Painting lines!"

    def chartest(self, sender):
        #self.superview['editor'].toolMode = 'chartest'
        if self.superview['editor'].color_check.hidden == True:
            self.superview['editor'].color_check.hidden = False
            self.superview['debugtext'].text = "Testing character colors!"
            self.superview['editor'].character_colorcheck()
        else:
            self.superview['editor'].color_check.hidden = True
        
    def dither(self, sender):
        if self.superview['editor'].drawDithered == False:
            self.superview['editor'].drawDithered = True
            self.subviews[0].subviews[11].background_color = 'black'
            self.subviews[0].subviews[11].tint_color = '#bababa'
        else:
            self.superview['editor'].drawDithered = False
            self.subviews[0].subviews[11].background_color = '#bababa'
            self.subviews[0].subviews[11].tint_color = 'black'

    def grid (self, sender):
        self.superview['editor'].gridOpacity = self.superview['editor'].grid_layout.alpha = self.superview['editor'].grid_layout.alpha - 0.5
        if self.superview['editor'].gridOpacity < 0:
            self.superview['editor'].darkGrid = not self.superview['editor'].darkGrid
            print ("Darkgrid: " + str(self.superview['editor'].darkGrid))
            self.superview['editor'].grid_layout.image = self.superview['editor'].draw_grid_image()
            self.superview['editor'].gridOpacity = self.superview['editor'].grid_layout.alpha = 1.0
        return True

    def zoom (self, sender):
        if self.superview['editor'].zoomState == False:
            self.superview['editor'].zoom_frame.hidden = False
            if self.superview['editor'].toolMode != 'zoom':
                self.superview['editor'].prevMode = self.superview['editor'].toolMode
            # The zoom tool action will now be used
            self.superview['editor'].toolMode = 'zoom'
            self.superview['debugtext'].text = "Entering zoom mode"

        elif self.superview['editor'].zoomState == True:
            self.superview['editor'].zoom_frame.hidden = True
            self.superview['editor'].toolMode = self.superview['editor'].prevMode
            self.superview['editor'].zoomState = False
            self.superview['editor'].redraw_canvas()
            self.superview['editor'].preview_update()
            if self.superview['editor'].color_check.hidden == False:
                self.superview['editor'].character_colorcheck()
            self.superview['debugtext'].text = "Leaving zoom mode"
            

    def changezoom (self, sender):
        prevCenter = self.superview['editor'].get_zoom_center()
        if self.pixel_editor.zoomCurrent == len(self.superview['editor'].zoomLevels)-1:
            self.superview['editor'].zoomCurrent = 0
        else:
            self.superview['editor'].zoomCurrent += 1
        self.superview['editor'].set_zoom_size()
        self.superview['editor'].set_zoom_center(prevCenter)
        self.superview['debugtext'].text = "Zoom level: " + str(self.superview['editor'].zoomLevels[self.superview['editor'].zoomCurrent])

        # Redraw canvas if we are zoomed in
        if self.superview['editor'].zoomState == True:
            self.superview['editor'].redraw_canvas()
            if self.superview['editor'].color_check.hidden == False:
                self.superview['editor'].character_colorcheck()

    @ui.in_background
    def load(self, sender):
        input_file = console.input_alert('Load Image')
        file_name = "images/" + input_file
        if isfile(file_name):
            self.superview['editor'].imageName = input_file[:-4]
            if self.superview['editor'].zoomState == True:
                self.zoom(sender)
            print ("Loading '" + file_name + "' into editor.")
            self.superview['editor'].loadimage(file_name)
            print "Done loading!"
            return True
        else:
            console.hud_alert('File does not exist')
            return False

    @ui.in_background
    def save(self, sender):
        if self.pixel_editor.has_image():
            image = self.pixel_editor.get_image()
            option = console.alert('Save Image', '', 'Camera Roll', 'New File', 'Copy image')
            if option == 1:
                photos.save_image(self.superview['preview'].image)
                console.hud_alert('Saved to cameraroll')
            elif option == 2:
                # Saves image to disk
                imageName = console.input_alert('Save Image')
                fileName = ('images/' + imageName + '.png')
                if isfile(fileName):
                    console.hud_alert('File exist!','error')
                    return False
                self.pixel_editor.imageName = imageName
                #name = 'images/image_{}.png'
                #get_num = lambda x=1: get_num(x+1) if isfile(name.format(x)) else x
                #file_name = name.format(get_num())
                pixels_to_png(self.superview['editor'].background_color, self.pixel_editor.pixels, self.pixel_editor.row*2, self.pixel_editor.column, fileName)
                console.hud_alert('Image saved as "{}"'.format(fileName))
            elif option == 3:
                clipboard.set_image(image, format='png')
                console.hud_alert('Copied')
        else:
            self.show_error()

    def undo(self, sender):
        ## Todo: undo function!
        ##
        print "Undo!"
        #self.pixel_editor.undo()

    #@ui.in_background
    def preview(self, sender):
        previewMode = self.superview['editor'].previewMode
        if previewMode == 2:
            self.superview['preview'].hidden = True
            self.superview['editor'].previewMode = 0
        elif previewMode == 0:
            self.superview['preview'].hidden = False
            self.superview['preview'].width = Settings.width
            self.superview['preview'].height = Settings.height
            self.superview['preview'].y = 560
            self.superview['editor'].previewMode = 1
        elif previewMode == 1:
            self.superview['preview'].hidden = False
            self.superview['preview'].width = Settings.width * 2
            self.superview['preview'].height = Settings.height * 2
            self.superview['preview'].y = 560 - Settings.height
            self.superview['editor'].previewMode = 2
        
    # Not used at the moment
    def preview_big_window(self, sender):
        if self.pixel_editor.has_image():
            v = ui.ImageView(frame=(100,100,320,200))
     
            # CRT Emulation
            im = self.pixel_editor.get_image()
            # insert CRT emulation here
            v.image = im
    
            v.width, v.height = v.image.size
            v.present('popover', popover_location=(100, 100), hide_title_bar=True)
        else:
            self.show_error()
    
    def trash(self, sender):
        if self.pixel_editor.has_image():
            trashMsg = 'Are you sure you want to clear the editor? Image will not be saved.'
            if console.alert('Trash', trashMsg, 'Yes'):
                self.pixel_editor.reset()
        else:
            self.show_error()

    def exit(self, sender):
        try:
            self.superview['editor'].fastsave(self.superview['editor'].imageName + "_tempsave")
        except Exception,e: 
            print str(e)
        msg = 'Are you sure you want to quit the pixel editor?'
        if console.alert('Quit', msg, 'Yes'):
            self.superview.close()
        else:
            self.show_error()
        return True

    

v = ui.load_view('c64_painter')
toolbar = v['toolbar']
toolbar.pixel_editor = v['editor']
for subview in toolbar.subviews:
    toolbar.init_actions(subview)
v.present(style = 'full_screen', orientations=['landscape'], hide_title_bar=True)
# If a temporary save exist, we load it into the editor
if isfile("images/_tempsave.png"):
   v['editor'].loadimage("images/_tempsave.png", False)
v['editor'].preview_init()
