#!python2

# Pythonista C64 Painter AKA Redux Paint
#
# Personal project for learning Python
# Warning, in these waters there be monsterously messy code!
#
# Based on the Pythonista Pixel Editor by Sebastian Jarsve
# Modified by Rune Spaans
#
#
# Features Todo:
# - Zoom mode
# - Brush size
# - New icons
# - Autosave every 20 seconds and at exit
# - Enter name when saving image
# v Find nearest colour when loading image
# - Preview view that always draws small image, and moves away depending on draw position
# - New undo-system. Hold a number of stroke undos, not per-pixel history.
# - Set grid opacity
# v Images saved in subfolder
# v Move load/save icons to start of icon-row
# v Selecting colour twice sets BG colour
# - Make colour set to BG draw as transparent?
# - Clash test tool button
# - Draw checkered/simple dither
# - Add CRT-effect to preview
# v Full-screen with no Pythonista title bar
# v Switch between gradient and 0-F order of colours
#
#
# Fixes/Bugs Todo:
#
# v Delete prevPixel after completing a stroke
# - Code changes have resulted in multiple duplicate functions, go through and clean up
# v Move more settings variables to the outermost scope
# v General functions for converting 0-255 rgb to 0..1 rgb
# - Zoom function sometimes ends by drawing a pixel, should not do that

import console
import scene
import photos
import clipboard
import ui
import Image
#import ImageFilter

from io import BytesIO
from os.path import isfile
from time import clock, sleep


# Settings used across the editor
class Settings (object):
    undoSteps = 20
    width = 320
    height = 200
    pixelSize = 2 # Made to be only 1 or 2
    actualWidth = width / pixelSize
    charSize = 8
    maxCharCol = 3 # Max colors per character, EXCLUDING bg color
    c64color_palette = [ (0, 0, 0), (255, 255, 255), (158, 59, 80), (133, 233, 209), (163, 70, 182), (93, 195, 94), (61, 51, 191), (249, 255, 126), (163, 98, 33), (103, 68, 0), (221, 121, 138), (86, 89, 86), (138, 140, 137), (182, 253, 184), (140, 128, 255), (195, 195, 193) ]
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


def closest_in_palette(matchColor):
    i = 0
    bestDelta = 1000
    c = 0
    for color in Settings.c64color_palette:
        r = sorted((color[0],matchColor[0]))
        g = sorted((color[1],matchColor[1]))
        b = sorted((color[2],matchColor[2]))
        delta = r[1]-r[0] + g[1]-g[0] + b[1]-b[0]
        if delta < bestDelta:
            i = c
            bestDelta = delta
        c = c + 1
    return Settings.c64color_palette[i]


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


def ui_to_pil(img):
    return Image.open(io.BytesIO(img.to_png()))


def pixels_to_png(bg_color, pixels, width, height, filename):
    # Create image
    bgColor = (int(bg_color[0]*255), int(bg_color[1]*255), int(bg_color[2]*255))
    im = Image.new("RGB", (width, height), bgColor)
    debugcounter = 0
    # Fill with pixels
    for p in pixels:
        # convert pixel data from RGBA 0..1 to RGB 0..255
        pixelCol = bgColor
        if p.colors[-1][3] != 0:
            pixelCol = (int(p.colors[-1][0]*255), int(p.colors[-1][1]*255), int(p.colors[-1][2]*255))
            im.putpixel((int(p.position[0]*2),p.position[1]),pixelCol)
            im.putpixel((int(p.position[0]*2)+1,p.position[1]),pixelCol)
        if debugcounter < 20: print ("Color at " + str(p.position) + ": " + str(p.colors[-1]))
        debugcounter = debugcounter + 1
    # save
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

    return charArray


# The Pixel, an array of these holds the current image
class Pixel (object):
    def __init__(self, x, y, w, h):
        self.rect = scene.Rect(x, y, w, h)  # Important: (x,y) is the lower-left corner
        self.colors = [(0, 0, 0, 0)]
        self.index = 0                      # Used to find neighbors
        self.position = (x,y)               # Used when writing images

    def used(self):
        return len(self.colors) > 1 and self.colors[-1] != (0, 0, 0, 0)

    def undo(self):
        if len(self.colors) > 1:
            self.colors.pop() # Removes last item in colors array


class PixelEditor(ui.View):
    # 1: 1x1 pixel, 2: 1x2 pixels, 3: 2x4 pixels, 4: character (4x8 pixels)
    brushSize = 1
    toolMode = 'dots'
    prevMode = 'dots'
    drawDithered = False
    prevPixel = []

    # The various zoom levels
    zoomLevels = (2, 3, 6, 9)
    zoomCurrent = 1 # What level we're currently zooming to
    zoomState = False

    # Last autosave time
    lastSave = 0

    def did_load(self):
        self.row = Settings.width/Settings.pixelSize
        self.column = Settings.height
        self.lastSave = int(clock())
        self.pixels = []
        self.pixel_path = []
        self.image_view = self.create_image_view()
        self.grid_layout = self.create_grid_layout()
        self.zoom_frame = self.create_zoom_frame()
        self.grid_opacity = 1.0
        self.current_color = (1, 1, 1, 1)

    def checkDither(self, position):
        if self.drawDithered == False: return True
        if is_odd(position[0]) and is_odd(position[1]) or is_odd(position[0]+1) and is_odd(position[1]+1):
            return False
        else: return True

    def has_image(self):
        if self.pixel_path:
            if [p for p in self.pixel_path if p.used()]:
                return True
        return False

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
    
    # Sets image in both views
    def set_image(self, image=None):
        # Image is set to provided image or a new is created
        image = image or self.create_new_image()
        if self.zoomState == False:
            # Sets both main image and the smaller preview image
            self.image_view.image = self.superview['preview'].image = image
        if self.zoomState == True:
            ## Todo: Change this to draw separate image for preview
            ## Or, draw small zoomed image and comp over?
            self.image_view.image = image

    def get_image(self):
        image = self.image_view.image
        return image

    def add_history(self, pixel):
        self.pixel_path.append(pixel)

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
            ui.set_color((0.5,0.5,0.5,0.25))
            path.stroke()
            # Grid line per character
            for y in xrange(self.column/8):
                for x in xrange(self.row/4):
                    #pixel = Pixel(x*s*8, y*s*8, s*8, s*8)
                    #charpath.append_path(ui.Path.rect(*pixel.rect))
                    charpath.append_path(ui.Path.rect(x*s*8, y*s*8, s*8, s*8))
            ui.set_color((1,1,1,0.25))
            charpath.stroke()
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

    def create_new_image(self):
        path = ui.Path.rect(*self.frame)
        with ui.ImageContext(self.width, self.height) as ctx:
            ui.set_color((0, 0, 0, 0))
            path.fill()
            return ctx.get_image()

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
            ui.set_color((0.5,0.5,0.5,0.5))
            pixelGrid.stroke()
            # Grid line per character
            for y in xrange(int(startPos[1]/charSize)*charSize, endPos[1]+1, charSize):
                for x in xrange(int(startPos[0]/charSize*charSize), endPos[0]+1,4):
                    characterGrid.append_path(ui.Path.rect((x-startPos[0])*pixelScale*2, (y-startPos[1])*pixelScale, pixelScale*charSize, pixelScale*charSize))
            ui.set_color((1,1,1,0.5))
            characterGrid.stroke()
            return ctx.get_image()    
        
    # Redraws the canvas
    def redraw_canvas(self):
        # Gets the pixels covered by the current zoom level
        zoomPixels = self.position_pixels()
        # Redraw view
        self.image_view.image = self.create_new_image()
        with ui.ImageContext(self.width, self.height) as ctx:
            for i in zoomPixels:
                p = self.pixels[i]
                #path = ui.Path.rect(*curPixel.rect)
                ui.set_color(p.colors[-1])
                pixel_path = ui.Path.rect(p.rect[0],p.rect[1],p.rect[2],p.rect[3])
                pixel_path.line_width = 0.5
                pixel_path.fill()
                pixel_path.stroke()
            self.image_view.image = ctx.get_image()
            ## Todo: insert drawing of preview window:
        # Redraw grid
        self.grid_layout.image = self.draw_grid_image()
        #self.grid_layout.hidden = True # Hide grid temporarily
        return True

    # Redraws the entire image based on what is stored in
    # pixel_editor.pixel_path. Done after undo.
    def create_image_from_history(self):
        path = ui.Path.rect(*self.frame)
        with ui.ImageContext(self.width, self.height) as ctx:
            for pixel in self.pixel_path:
                if not pixel.used():
                    continue
                ui.set_color(pixel.colors[-1])
                pixel_path = ui.Path.rect(*pixel.rect)
                pixel_path.line_width = 0.5
                pixel_path.fill()
                pixel_path.stroke()
            img = ctx.get_image()
            return img

    def reset(self, row=None, column=None):
        self.pixels = []
        self.pixel_path = []
        self.grid_layout.image = self.init_pixel_grid()
        self.set_image()

    def undo(self):
        if self.pixel_path:
            pixel = self.pixel_path.pop() # remove last array item
            pixel.undo()
            self.set_image(self.create_image_from_history())

    def pencil(self, pixel):
        if pixel.colors[-1] != self.current_color:
            pixel.colors.append(self.current_color)
            self.pixel_path.append(pixel)
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
                if curPixel.colors[-1] != self.current_color and self.checkDither(curPixel.position):
                    curPixel.colors.append(self.current_color)
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
        if pixel.colors[-1] != self.current_color:
                #if self.drawDithered == False or (is_odd(pixel.position[0]) and is_odd(pixel.position[1]) or is_odd(pixel.position[0]+1) and is_odd(pixel.position[1]+1)):
            if self.checkDither(pixel.position):
                pixel.colors.append(self.current_color)
                self.pixel_path.append(pixel)
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
                ui.set_color(p.colors[-1])
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
            # Auto-save image every 20 seconds of painting
                saveDelta = int(clock()) - self.lastSave
                if saveDelta > 20:
                    ## Todo: Add autosave here
                    print 'Autosave'
                    self.lastSave = int(clock())
                if self.toolMode == 'dots':
                    self.drawpixel(pixel)
                    if self.toolMode == 'lines' or self.toolMode == 'dots':
                        self.superview['debugtext'].text = "index:" + str(pixel.index) + ", pos:" + str(pixel.position) + ", touch:" + touchState + ", saveDelta:" + str(saveDelta)

                elif self.toolMode == 'lines':
                    if touchState == 'began':
                        self.prevPixel == []
                    self.drawline(self.prevPixel, pixel, touchState)
                    self.prevPixel = pixel
                    if touchState == "ended":
                        ## Todo: update preview image at end of each stroke
                        self.prevPixel = []
                    if self.toolMode == 'lines' or self.toolMode == 'dots':
                        self.superview['debugtext'].text = "index:" + str(pixel.index) + ", pos:" + str(pixel.position) + ", touch:" + touchState + ", saveDelta:" + str(saveDelta)

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

                        # Return to previous tool mode
                        self.toolMode = self.prevMode
                        self.superview['debugtext'].text = "Mode set back to " + self.toolMode
                        # Sometime, random dots get drawn after this command

                # Debug text
                #if self.toolMode == 'lines' or self.toolMode == 'dots':
                #  self.superview['debugtext'].text = "index:" + str(pixel.index) + ", pos:" + str(pixel.position) + ", touch:" + touchState + ", saveDelta:" + str(saveDelta)


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
            self['bg_color'].background_color = color
            self.superview['editor'].background_color = color
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
        self.subviews[0].subviews[0].background_image = ui.Image.named('icons/paint_dots_64.png')
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

    def dither(self, sender):
        if self.superview['editor'].drawDithered == False:
            self.superview['editor'].drawDithered = True
            self.subviews[0].subviews[11].background_color = 'black'
            self.subviews[0].subviews[11].tint_color = '#bababa'
        else:
            self.superview['editor'].drawDithered = False
            self.subviews[0].subviews[11].background_color = '#bababa'
            self.subviews[0].subviews[11].tint_color = 'black'

    def zoom (self, sender):
        if self.superview['editor'].zoomState == False:
            self.superview['editor'].zoom_frame.hidden = False
            self.superview['editor'].prevMode = self.superview['editor'].toolMode
            # The zoom tool action will now be used
            self.superview['editor'].toolMode = 'zoom'
            self.superview['debugtext'].text = "Entering zoom mode"

        elif self.superview['editor'].zoomState == True:
            self.superview['editor'].zoom_frame.hidden = True
            self.superview['editor'].toolMode = self.superview['editor'].prevMode

            # Todo: insert redraw views
            self.superview['editor'].zoomState = False
            self.superview['editor'].redraw_canvas()
            self.superview['debugtext'].text = "Leaving zoom mode"

    def changezoom (self, sender):
        prevCenter = self.superview['editor'].get_zoom_center()
        if self.superview['editor'].zoomCurrent == len(self.superview['editor'].zoomLevels)-1:
            self.superview['editor'].zoomCurrent = 0
        else:
            self.superview['editor'].zoomCurrent += 1
        self.superview['editor'].set_zoom_size()
        self.superview['editor'].set_zoom_center(prevCenter)
        self.superview['debugtext'].text = "Zoom level: " + str(self.superview['editor'].zoomLevels[self.superview['editor'].zoomCurrent])

        # Redraw canvas if we are zoomed in
        if self.superview['editor'].zoomState == True:
            self.superview['editor'].redraw_canvas()

    def trash(self, sender):
            #if self.pixel_editor.has_image():
        trashMsg = 'Are you sure you want to clear the editor? Image will not be saved.'
        if console.alert('Trash', trashMsg, 'Yes'):
            self.pixel_editor.reset()
        else:
            self.show_error()

    @ui.in_background
    def load(self, sender):
        file_name = "images/" + console.input_alert('Load Image')
        if isfile(file_name):
            print ("Loading '" + file_name + "' into editor.")
            loadImg = file_to_img(self.pixel_editor.row, self.pixel_editor.column, file_name)
            img = self.superview['editor'].create_new_image()
            charRowSize = Settings.actualWidth * Settings.charSize
            # We read and draw the image one character line at a time
            for charRow in xrange(0, Settings.height/Settings.charSize):
                indexArray = []
                startIndex = charRow*charRowSize
                endIndex = charRow*charRowSize + charRowSize
                #print ("Importing subrow: " + str(startIndex) + ", " + str(endIndex))
                for i in xrange(startIndex, endIndex):
                    indexArray.append(i)
                    pixelCol = loadImg.getpixel(self.pixel_editor.pixels[i].position)
                    # Find the closest color in the C64 palette
                    pixelCol = closest_in_palette(pixelCol)
                    self.superview['editor'].pixels[i].colors.append(color_to_1(pixelCol))
                img = self.superview['editor'].draw_index_array(img, indexArray)
                self.superview['editor'].set_image(img)
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
                photos.save_image(image)
                console.hud_alert('Saved to cameraroll')
            elif option == 2:
                # Saves image to disk
                name = 'images/image_{}.png'
                get_num = lambda x=1: get_num(x+1) if path.isfile(name.format(x)) else x
                file_name = name.format(get_num())
                pixels_to_png(self.superview['editor'].background_color, self.pixel_editor.pixels, self.pixel_editor.row*2, self.pixel_editor.column, file_name)
                console.hud_alert('Image saved as "{}"'.format(file_name))
            elif option == 3:
                clipboard.set_image(image, format='png')
                console.hud_alert('Copied')
        else:
            self.show_error()

    def exit(self, sender):
        msg = 'Are you sure you want to quit the pixel editor?'
        if console.alert('Quit', msg, 'Yes'):
            self.superview.close()
        else:
            self.show_error()
        return True

    def tempsave(self):
        print('Saving temp image...')
        if self.pixel_editor.has_image():
        # This does not work.. Why??
            image = self.pixel_editor.image_view.get_image()
            print('Image type is: ' + str(type(image)))
            file_name = 'images/tempsave.png'
            print('Filename: ' + file_name)
            with open(file_name, 'w') as f:
                print("Step 2")
                ui_to_pil(image).save(f, 'png')
                print("Step 3")
            print('Image saved as ' + file_name)
        else:
            print ("No image found!")
            exit()

    def undo(self, sender):
        self.pixel_editor.undo()

    @ui.in_background
    def preview(self, sender):
        if self.pixel_editor.has_image():
            v = ui.ImageView(frame=(100,400,320,200))

            # CRT Emulation
            im = self.pixel_editor.get_image()
            # insert CRT emulation here
            v.image = im

            v.width, v.height = v.image.size
            v.present('popover', popover_location=(200, 275), hide_title_bar=True)
        else:
            self.show_error()

v = ui.load_view('c64_painter')
toolbar = v['toolbar']
toolbar.pixel_editor = v['editor']
for subview in toolbar.subviews:
    toolbar.init_actions(subview)
v.present(style = 'full_screen', orientations=['landscape'], hide_title_bar=True)

