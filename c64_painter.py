#!python2

# Based on the Pythonista Pixel Painter
#
#
# Todo:
# - Zoom 3x, Zoom 6x (draw portion of image?)
# - Undo
# - Brush size
# - Autosave every 20 seconds and at exit
# v Images saved in subfolder
# v Move load/save icons to start of icon-row
# - Find nearest colour when loading image
# v Selecting colour twice sets BG colour
# - Make colour set to BG transparent
# - Clash test
# - Draw checkered/simple dither
# - Preview with crt effect
# v Full-screen with no Pythonista title bar
# v Switch between gradient and 0-F order of colours
# - General functions for converting 0-255 rgb to 0..1 rgb

import console, scene, photos, clipboard, ui, io, os.path, Image, ImageFilter, time, sys, atexit

def pil_to_ui(img):
    with io.BytesIO() as bIO:
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
	
def png_to_pixels(width, height, filename):
	im = Image.open(filename)
	im = im.resize((width, height), Image.NEAREST)
	# Find nearest colour to C64 palette using sympy.distance
	
	#im.save("temp_" + filename)
	return im
	
def xy_to_index(xcoord,ycoord):
	arrayIndex = ycoord*160 + xcoord + 1
	return arrayIndex

def index_to_xy(arrayIndex):
	ycoord = int(arrayIndex/160)
	xcoord = arrayIndex-(160*ycoord)-1
	return (xcoord,ycoord)


# The Pixel class, derived from a featureless 'object'
class Pixel (object):
    def __init__(self, x, y, w, h):
        self.rect = scene.Rect(x, y, w, h) # Rect class is used for bounding boxes and other rectangle values. (x,y) is its lower-left corner
        self.colors = [(0, 0, 0, 0)]
        self.index = 0 						# Used to find neighbors
        self.position = (x,y) 		# Used when writing images
        
    def used(self):
        return len(self.colors) > 1 and self.colors[-1] != (0, 0, 0, 0)
        
    def undo(self):
        if len(self.colors) > 1:
            self.colors.pop() # Removes last item in colors array


class PixelEditor(ui.View):
    # 1: 1x1 pixel, 2: 1x2 pixels, 3: 2x4 pixels, 4: character (4x8 pixels)
    pixelSize = 1
    paintMode = 'dots'
    prevPixel = []
    lastSave = 0 # Last autosave time
    	
    def did_load(self):
        self.row = 160
        self.column = 200
        self.lastSave = int(time.clock())
        self.pixels = []
        self.pixel_path = []
        self.image_view = self.create_image_view()
        self.grid_layout = self.create_grid_layout()
        self.current_color = (1, 1, 1, 1)
        self.mode = 'pencil'
        self.auto_crop_image = False 
        
    def has_image(self):
        if self.pixel_path:
            if [p for p in self.pixel_path if p.used()]:
                return True 
        return False 

		# Sets image in both views
    def set_image(self, image=None):
    		# ?? why the 'or'?
        image = image or self.create_new_image()
        # Sets both views
        self.image_view.image = self.superview['preview'].image = image
        
    def get_image(self):
        image = self.image_view.image
        return image
        
    def add_history(self, pixel):
        self.pixel_path.append(pixel)

		# Draws pixel grid and pixel overlay
    def create_grid_image(self):
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
                    # Fills image with pixels? 
                    # Changing this changes the pixel aspect
                    pixel = Pixel(x*s*2, y*s, s*2, s)
                    pixel.index = len(self.pixels) + 1
                    pixel.position = (x,y)
                    path.append_path(ui.Path.rect(*pixel.rect))
                    self.pixels.append(pixel) #Adds this pixel to the pixels list
            ui.set_color((0.5,0.5,0.5,0.25))
            path.stroke()
            # Grid line per character
            for y in xrange(self.column/8):
                for x in xrange(self.row/4):
                    pixel = Pixel(x*s*8, y*s*8, s*8, s*8)
                    charpath.append_path(ui.Path.rect(*pixel.rect))
            ui.set_color((1,1,1,0.25))
            charpath.stroke()
            return ctx.get_image()

    def create_grid_layout(self):
        image_view = ui.ImageView(frame=self.bounds)
        image_view.image = self.create_grid_image()
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
        self.grid_layout.image = self.create_grid_image()
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
                    old_img.draw() # Draw image into rectangle in current context, no parameters means natural size
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
      # Debug, try and figure out which pixel we are over
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
        #self.current_color = 'white'
        self.drawpixel(pixel)
      else:
        #self.current_color = 'red'
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
        #self.superview['debugtext'].text = "lineDraw"
        # Update all pixel objects along the drawn line
        for c in range(1, max(xDist,yDist)):
          #self.current_color = 'orange'
          if yDist >= xDist:
            curPixel = self.pixels[ xy_to_index( int(xStart+(yIncr*c*xDir)-0.5), int(yStart+(c*yDir)) ) ]
          else:
            curPixel = self.pixels[ xy_to_index( xStart+(xDir*c)-1, int(yStart+(xIncr*c*yDir)) ) ]
          if curPixel.colors[-1] != self.current_color:
            curPixel.colors.append(self.current_color)
            linePixels.append(curPixel)
        # Redraw the image    
        old_img = self.image_view.image
        with ui.ImageContext(self.width, self.height) as ctx:
          if old_img:
            old_img.draw() # Draw image into rectangle in current context, no parameters means natural size
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
        pixel.colors.append(self.current_color)
        self.pixel_path.append(pixel)
        old_img = self.image_view.image
        path = ui.Path.rect(*pixel.rect)
        with ui.ImageContext(self.width, self.height) as ctx:
          if old_img:
            old_img.draw() # Draw image into rectangle in current context, no parameters means natural size
          ui.set_color(self.current_color)
          pixel_path = ui.Path.rect(*pixel.rect)
          pixel_path.line_width = 0.5
          pixel_path.fill()
          pixel_path.stroke()
          self.set_image(ctx.get_image())

    def action(self, touch, touchState):
        p = scene.Point(*touch.location)
        for pixel in self.pixels:
          if p in pixel.rect:
            # Auto-save image every 20 seconds of painting
            saveDelta = int(time.clock()) - self.lastSave
            if saveDelta > 20: 
              print 'Autosave' # !! Add autosave here !!
              self.lastSave = int(time.clock())
            if self.paintMode == 'dots':
              self.drawpixel(pixel)
            elif self.paintMode == 'lines':
              self.drawline(self.prevPixel, pixel, touchState)
            self.prevPixel = pixel
            self.superview['debugtext'].text = "index:" + str(pixel.index) + ", pos:" + str(pixel.position) + ", touch:" + touchState + ", saveDelta:" + str(saveDelta)
                                          
    def touch_began(self, touch):
        self.action(touch, "began")

    def touch_moved(self, touch):
        self.action(touch, "moved")    
        
    def touch_ended(self, touch):
        self.action(touch, "ended")
        
        
class ColorView (ui.View):
    c64color_palette = [ (0, 0, 0), (255, 255, 255), (158, 59, 80), (133, 233, 209), (163, 70, 182), (93, 195, 94), (61, 51, 191), (249, 255, 126), (163, 98, 33), (103, 68, 0), (221, 121, 138), (86, 89, 86), (138, 140, 137), (182, 253, 184), (140, 128, 255), (195, 195, 193) ]
    
    c64color_labels = [ "black", "white", "red", "cyan", "purple", "green", "blue", "yellow", "orange", "brown", "pink", "darkgrey", "grey", "lightgreen", "lightblue", "lightgrey"]
    
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
          subview.background_color = (self.c64color_palette[num][0]/255.0, self.c64color_palette[num][1]/255.0, self.c64color_palette[num][2]/255.0)
          subview.title = self.c64hex[num]
          num = num + 1
        self.palette_type = "gradient"
        self.subviews[3].title = "0-F"
        #self.superview['debugtext'].text = "Palette set to numeric"
      elif self.palette_type == 'gradient':
        for subview in self['palette'].subviews:
          subview.background_color = (self.c64color_palette[self.c64color_gradient[num]][0]/255.0, self.c64color_palette[self.c64color_gradient[num]][1]/255.0, self.c64color_palette[self.c64color_gradient[num]][2]/255.0)
          subview.title = self.c64hex[self.c64color_gradient[num]]
          num = num + 1
        self.palette_type = "numeric"
        self.subviews[3].title = "grad"
        #self.superview['debugtext'].text = "Palette set to gradient"
                  
    def get_color(self):
        return tuple(self.color[i] for i in 'rgba')

    def set_color(self, color=None):
        color = color or self.get_color()
        if self['current_color'].background_color == color:
          self['current_color'].background_color = self.superview['editor'].current_color = self['bg_color'].background_color
          self['bg_color'].background_color = color
          self.superview['editor'].background_color = color
        else:
          self['current_color'].background_color = color
          self.superview['editor'].current_color = color
          self.superview['debugtext'].text = "Color set to " + str(color)

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
      self.superview['editor'].paintMode = 'dots'
      self.superview['debugtext'].text = "Painting dots!"
      
    def paintlines(self, sender):
      self.superview['editor'].paintMode = 'lines'
      self.superview['debugtext'].text = "Painting lines!"
      
    def zoom (self, sender):
      self.superview['debugtext'].text = "setting scale " + str(self.pixel_editor.width)
      self.superview['editor'].image_view.image.scale = 2.0  	
                
    def trash(self, sender):
        #if self.pixel_editor.has_image():
        msg = 'Are you sure you want to clear the pixel editor? Image will not be saved.'
        if console.alert('Trash', msg, 'Yes'):
            self.pixel_editor.reset()
        else: 
            self.show_error()
    
    @ui.in_background                        
    def load(self, sender):
      file_name = "images/" + console.input_alert('Load Image')
      if os.path.isfile(file_name): 
        im = png_to_pixels(self.pixel_editor.row, self.pixel_editor.column, file_name)
        print ("Loading '" + file_name + "' into editor.")
        for p in self.pixel_editor.pixels:
          pixelCol = im.getpixel(p.position)
          # Convert image data from 0...255 to 0..1
          p.colors.append((float(pixelCol[0])/255, float(pixelCol[1])/255, float(pixelCol[2])/255, 1.0))
          self.pixel_editor.pixel_path.append(p)
        #Update image with our new pixels
        old_img = self.superview['editor'].image_view.image
        with ui.ImageContext(self.pixel_editor.width, self.pixel_editor.height) as ctx:
          if old_img:
              old_img.draw()
          for p in self.pixel_editor.pixels:
            #path = ui.Path.rect(*curPixel.rect)
            ui.set_color(p.colors[-1])
            pixel_path = ui.Path.rect(p.rect[0],p.rect[1],p.rect[2],p.rect[3]) # create path with rectangle
            pixel_path.line_width = 0.5
            pixel_path.fill()
            pixel_path.stroke()
          self.superview['editor'].set_image(ctx.get_image())
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
              get_num = lambda x=1: get_num(x+1) if os.path.isfile(name.format(x)) else x
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
        image = self.pixel_editor.get_image()
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


# Temp save image when exiting
# Does not work, @atexit executes at startup, not at exit!
@atexit.register
def _exitcb():
	print('Exit')
try:
	print("Pixels in memory: " + str(len(toolbar.pixel_editor.pixels)))
	#pixels_to_png((toolbar.pixel_editor.pixels), 80, 100, "tempsave.png")
	#toolbar.pixel_editor.tempsave()
except Exception,e:
	print str(e)
