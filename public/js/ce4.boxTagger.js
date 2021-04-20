// Copyright (c) 2014 Lazy 8 Studios, LLC.
// All rights reserved.
// ce4.boxTagger contains specialized UI code for viewing and tagging photos on mobile devices.
//------------------------------------------------------------------------------
goog.provide("ce4.boxTagger");

goog.require("ce4.util");

ce4.boxTagger = {
    init: function(imgSrc, highResSrc, is_panorama, cbImgLoad, cbTagChange, cbHideLoader, yaw)
    {
        // Constants
        this.HEADER_HEIGHT = $('#id-game-header-mobile').height();
        this.ICON_SIZE = 44;
        this.BOX_ACTION_DRAG = 0;
        this.BOX_ACTION_RESIZE = 1;
        this.BOX_ACTION_CLOSE = 2;
        // Set min and max box sizes to 70 and 500 pixels.
        this.MIN_BOX_SIZE_STANDARD = 0.0875;  // =70/600/1.333
        this.MIN_BOX_SIZE_PANO     = 0.0292;  // =70/600/4.0
        this.MAX_BOX_SIZE_STANDARD = 0.625;   // =500/600/1.333
        this.MAX_BOX_SIZE_PANO     = 0.208;   // =500/600/4.0

        // Callbacks.
        this.cbImgLoad    = cbImgLoad;
        this.cbTagChange  = cbTagChange;
        this.cbHideLoader = cbHideLoader;
        this.cbCancelSelection = undefined;

        this.yaw = yaw;
        this.is_panorama = is_panorama;
        this.min_box_size = this.MIN_BOX_SIZE_STANDARD;
        this.max_box_size = this.MAX_BOX_SIZE_STANDARD;
        this.aspect = 1.33333;
        if (this.is_panorama) {
            this.min_box_size = this.MIN_BOX_SIZE_PANO;
            this.max_box_size = this.MAX_BOX_SIZE_PANO;
            this.aspect = 4.0;
        }
        this.photoCanvas = document.getElementById('photoCanvas');
        this.ctx = photoCanvas.getContext("2d");
        this.boxes = [];
        this.selectedBox = -1;
        this.boxAction = this.BOX_ACTION_DRAG;

        // We need a callback to resize our canvas if the orientation changes.
        jQuery(window).on("resize", ce4.boxTagger.onResize);

        // Icons that will be drawn to the canvas.
        this.iconResize = new Image();
        this.iconResize.src = ce4.util.url_static('/static/img/ui/mobile_icon_resize.png');
        this.iconClose = new Image();
        this.iconClose.src = ce4.util.url_static('/static/img/ui/mobile_icon_close.png');

        this.mc = new Hammer.Manager(photoCanvas);

        // Add the events we want to manage to the Manager.
        var hammerPinch = new Hammer.Pinch({ threshold: 0 });
        var hammerPan   = new Hammer.Pan();
        var hammerPress = new Hammer.Press({ time:0 });
        this.mc.add([hammerPinch, hammerPan, hammerPress]);
        this.mc.add(hammerPinch).recognizeWith(this.mc.get('pan'));
        
        this.showing_infrared = false;
        this.img = new Image();
        this.img.is_loaded = false;
        this.imgInfrared = new Image();
        this.imgInfrared.is_loaded = false;
        this.highResSrc = highResSrc;
        this.imgHighRes = new Image();
        this.imgHighRes.is_loaded = false;
        this.imgScale = 200.0;  // Displayed width in screen pixels.
        this.imgX = 0;          // Upper-left corner in screen coordinates.
        this.imgY = 0;

        this.dscale = 1.0;
        this.dx = 0;
        this.dy = 0;
        this.dxPinch = 0;  // These allow us to center the scaling around the pinch point.
        this.dyPinch = 0;

        this.mc.on("press", function(ev) {
            // Check if we've clicked inside a box.
            ce4.boxTagger.selectedBox = -1;
            // Normally, we just draw everything once, but for panoramas, we draw 3x to span the seam.
            var drawCopies = 1;
            if (ce4.boxTagger.is_panorama) drawCopies = 3;
            for (var copy=0; copy<drawCopies; copy++) {
                var offset = 0;
                if (copy == 1) offset = ce4.boxTagger.imgScale;
                if (copy == 2) offset = -ce4.boxTagger.imgScale

                for (var b=0; b<ce4.boxTagger.boxes.length; b++) {
                    var box = ce4.boxTagger.boxes[b];
                    if (box.is_locked) {
                        // We can't edit locked boxes.
                        continue;
                    }
                    var clickCoord = {'x':ev.center.x, 'y':ev.center.y-ce4.boxTagger.HEADER_HEIGHT};
                    var screenCoord0 = ce4.boxTagger.imageToScreen(box.x, box.y, ce4.boxTagger.imgX, ce4.boxTagger.imgY, ce4.boxTagger.imgScale);
                    var screenCoord1 = ce4.boxTagger.imageToScreen(box.x+box.width, box.y+box.height, ce4.boxTagger.imgX, ce4.boxTagger.imgY, ce4.boxTagger.imgScale);
                    screenCoord0.x += offset;
                    screenCoord1.x += offset;
                    // Inside the box?
                    if (clickCoord.x >= screenCoord0.x && clickCoord.x <= screenCoord1.x && clickCoord.y >= screenCoord0.y && clickCoord.y <= screenCoord1.y) {
                        ce4.boxTagger.selectedBox = b;
                        ce4.boxTagger.boxAction = ce4.boxTagger.BOX_ACTION_DRAG;
                    }
                    // Clicked the close icon?
                    if (clickCoord.x >= screenCoord1.x-ce4.boxTagger.ICON_SIZE/2 && clickCoord.x <= screenCoord1.x+ce4.boxTagger.ICON_SIZE/2
                     && clickCoord.y >= screenCoord0.y-ce4.boxTagger.ICON_SIZE/2 && clickCoord.y <= screenCoord0.y+ce4.boxTagger.ICON_SIZE/2) {
                        ce4.boxTagger.selectedBox = b;
                        ce4.boxTagger.boxAction = ce4.boxTagger.BOX_ACTION_CLOSE;
                    }
                    // Clicked the resize icon?
                    if (clickCoord.x >= screenCoord1.x-ce4.boxTagger.ICON_SIZE/2 && clickCoord.x <= screenCoord1.x+ce4.boxTagger.ICON_SIZE/2
                     && clickCoord.y >= screenCoord1.y-ce4.boxTagger.ICON_SIZE/2 && clickCoord.y <= screenCoord1.y+ce4.boxTagger.ICON_SIZE/2) {
                        ce4.boxTagger.selectedBox = b;
                        ce4.boxTagger.boxAction = ce4.boxTagger.BOX_ACTION_RESIZE;
                    }
                }
            }

            // Was a close box tapped?
            if (ce4.boxTagger.selectedBox != -1 && ce4.boxTagger.boxAction == ce4.boxTagger.BOX_ACTION_CLOSE) {
                ce4.boxTagger.removeBox(ce4.boxTagger.selectedBox);
                ce4.boxTagger.selectedBox = -1;
                ce4.boxTagger.cbTagChange();
            }

            ce4.boxTagger.redrawCanvas(false);
        });

        this.mc.on("panstart", function(ev) {
            ce4.boxTagger.dx = ev.deltaX;
            ce4.boxTagger.dy = ev.deltaY;
            ce4.boxTagger.redrawCanvas(false);
        });

        this.mc.on("panmove", function(ev) {
            ce4.boxTagger.dx = ev.deltaX;
            ce4.boxTagger.dy = ev.deltaY;
            ce4.boxTagger.redrawCanvas(false);

            // Panorama wrap-around:
            if (ce4.boxTagger.is_panorama && ce4.boxTagger.selectedBox == -1) {
                if (ce4.boxTagger.imgX+ce4.boxTagger.dx < -ce4.boxTagger.imgScale/2) {
                    ce4.boxTagger.imgX += ce4.boxTagger.imgScale;
                }
                if (ce4.boxTagger.imgX+ce4.boxTagger.dx > ce4.boxTagger.imgScale/2) {
                    ce4.boxTagger.imgX -= ce4.boxTagger.imgScale;
                }
            }
        });

        this.mc.on("panend", function(ev) {
            if (ce4.boxTagger.selectedBox == -1) {
                ce4.boxTagger.imgX += ev.deltaX;
                ce4.boxTagger.imgY += ev.deltaY;
            }
            else if (ce4.boxTagger.boxAction == ce4.boxTagger.BOX_ACTION_DRAG) {
                ce4.boxTagger.boxes[ce4.boxTagger.selectedBox].x += ev.deltaX/ce4.boxTagger.imgScale;
                ce4.boxTagger.boxes[ce4.boxTagger.selectedBox].y += ev.deltaY/ce4.boxTagger.imgScale;
                ce4.boxTagger.clampBoxPosition(ce4.boxTagger.boxes[ce4.boxTagger.selectedBox]);
                // Panorama wrap-around:
                if (ce4.boxTagger.is_panorama && ce4.boxTagger.boxes[ce4.boxTagger.selectedBox].x < 0.0) {
                    ce4.boxTagger.boxes[ce4.boxTagger.selectedBox].x += 1.0;
                }
                if (ce4.boxTagger.is_panorama && ce4.boxTagger.boxes[ce4.boxTagger.selectedBox].x > 1.0) {
                    ce4.boxTagger.boxes[ce4.boxTagger.selectedBox].x -= 1.0;
                }
            }
            else if (ce4.boxTagger.boxAction == ce4.boxTagger.BOX_ACTION_RESIZE) {
                ce4.boxTagger.boxes[ce4.boxTagger.selectedBox].width  += ev.deltaX/ce4.boxTagger.imgScale;
                ce4.boxTagger.boxes[ce4.boxTagger.selectedBox].height += ev.deltaY/ce4.boxTagger.imgScale;
                ce4.boxTagger.clampBoxSize(ce4.boxTagger.boxes[ce4.boxTagger.selectedBox]);
            }
            else {
                console.log("Warning: Unhandled boxTagger action "+ce4.boxTagger.boxAction);
            }
            ce4.boxTagger.dx = ce4.boxTagger.dy = 0;
            ce4.boxTagger.selectedBox = -1;

            // Clamp values.
            var clamped = ce4.boxTagger.clampImage(ce4.boxTagger.imgX, ce4.boxTagger.imgY, ce4.boxTagger.imgScale);
            ce4.boxTagger.imgX = clamped.x;
            ce4.boxTagger.imgY = clamped.y;
            ce4.boxTagger.imgScale = clamped.scale;

            // Panorama wrap-around:
            if (ce4.boxTagger.is_panorama && ce4.boxTagger.selectedBox == -1) {
                if (ce4.boxTagger.imgX < -ce4.boxTagger.imgScale/2) {
                    ce4.boxTagger.imgX += ce4.boxTagger.imgScale;
                }
                if (ce4.boxTagger.imgX > ce4.boxTagger.imgScale/2) {
                    ce4.boxTagger.imgX -= ce4.boxTagger.imgScale;
                }
            }

            ce4.boxTagger.redrawCanvas(true);
        });

        this.mc.on("pinchstart pinchmove", function(ev) {
            if (ce4.boxTagger.selectedBox != -1) {
                // No zooming while panning a box.
                return;
            }

            ce4.boxTagger.dscale = ev.scale;
            ce4.boxTagger.dx = ev.deltaX;
            ce4.boxTagger.dy = ev.deltaY;

            // Expressed in the image's homogeneous coordinages (e.g., img width = 1.0), what is the center point of the
            // scaling operation at the starting scale?
            var scale = ce4.boxTagger.clampMaxScale(ce4.boxTagger.imgScale * ce4.boxTagger.dscale);
            var x = ce4.boxTagger.imgX + ce4.boxTagger.dx;
            var y = ce4.boxTagger.imgY + ce4.boxTagger.dy;
            var imgCenterX = (ev.center.x - x)/ce4.boxTagger.imgScale;
            var imgCenterY = (ev.center.y - y)/ce4.boxTagger.imgScale;

            // Translate such that scaling occurs around our center point.
            // We want newCenterX = imgCenterX where newCenterX = (ev.center.x - x - dxPinch))/scale
            ce4.boxTagger.dxPinch = ev.center.x - x - imgCenterX*scale;
            ce4.boxTagger.dyPinch = ev.center.y - y - imgCenterY*scale;
            
            ce4.boxTagger.redrawCanvas();
        });

        this.mc.on("pinchend", function(ev) {
            if (ce4.boxTagger.selectedBox != -1) {
                // No zooming while panning a box.
                return;
            }

            ce4.boxTagger.imgScale *= ev.scale;
            ce4.boxTagger.dscale = 1.0;
            ce4.boxTagger.imgX += ce4.boxTagger.dxPinch;
            ce4.boxTagger.imgY += ce4.boxTagger.dyPinch;
            ce4.boxTagger.dxPinch = ce4.boxTagger.dyPinch = 0;

            // Clamp values.
            var clamped = ce4.boxTagger.clampImage(ce4.boxTagger.imgX, ce4.boxTagger.imgY, ce4.boxTagger.imgScale);
            ce4.boxTagger.imgX = clamped.x;
            ce4.boxTagger.imgY = clamped.y;
            ce4.boxTagger.imgScale = clamped.scale;

            ce4.boxTagger.redrawCanvas();
        });

        this.img.onload = function () {
            this.is_loaded = true;
            ce4.boxTagger.cbHideLoader()
            ce4.boxTagger.cbImgLoad();

            // Clamp the initial values.
            var clamped = ce4.boxTagger.clampImage(ce4.boxTagger.imgX, ce4.boxTagger.imgY, ce4.boxTagger.imgScale);
            ce4.boxTagger.imgX = clamped.x;
            ce4.boxTagger.imgY = clamped.y;
            ce4.boxTagger.imgScale = clamped.scale;

            // If this is a panorama image, zoom in until we have a 4:3 aspect ratio or we are exactly
            // the height of the canvas.
            if (ce4.boxTagger.is_panorama) {
                var aspectCanvas = ce4.boxTagger.ctx.canvas.width/ce4.boxTagger.ctx.canvas.height;
                if (aspectCanvas <= 4.0/3.0) {
                    // Zoom to 4:3 and letterbox top/bottom.
                    ce4.boxTagger.imgScale *= 3.0;
                }
                else {
                    // Zoom to fit image height to canvas height.
                    ce4.boxTagger.imgScale = ce4.boxTagger.ctx.canvas.height * ce4.boxTagger.img.width/ce4.boxTagger.img.height;
                }
                // Center panorama.
                ce4.boxTagger.imgX = -(ce4.boxTagger.imgScale-ce4.boxTagger.ctx.canvas.width)/2.0;
            }

            ce4.boxTagger.redrawCanvas(true);
        }

        this.imgInfrared.onload = function() {
            this.is_loaded = true;
            ce4.boxTagger.cbHideLoader();
            ce4.boxTagger.redrawCanvas(true);
        }

        this.imgHighRes.onload = function() {
            this.is_loaded = true;
            ce4.boxTagger.redrawCanvas(true);
        }
            
        ce4.boxTagger.onResize();
        this.img.src = imgSrc;
    },
    
    //------------------------------------------------------------------------------
    release: function() {
        jQuery(window).off("resize", ce4.boxTagger.onResize);
    },

    //------------------------------------------------------------------------------
    // When the window is resized, set the canvas to fill the window. Note that this is
    // NOT the same as changing the CSS width/height, which just scales the existing canvas.    
    onResize: function() {
        ce4.boxTagger.ctx.canvas.width = $(window).width();
        ce4.boxTagger.ctx.canvas.height = $(window).height()-ce4.boxTagger.HEADER_HEIGHT;
        ce4.boxTagger.redrawCanvas();

        // Clamp to our new size.
        var clamped = ce4.boxTagger.clampImage(ce4.boxTagger.imgX, ce4.boxTagger.imgY, ce4.boxTagger.imgScale);
        ce4.boxTagger.imgX = clamped.x;
        ce4.boxTagger.imgY = clamped.y;
        ce4.boxTagger.imgScale = clamped.scale;
    },
    
    //------------------------------------------------------------------------------
    // Clamp the translation and scale values for the image to make sure that it doesn't
    // get too small and, when letterboxed, it stays centered.
    clampImage: function(x, y, scale) {
        var clamped = {'x':x, 'y':y, 'scale':scale};
        var minScale, maxScale, minX, maxX, minY, maxY;
        
        // Max scale at 1 texel per pixel for the high-res image.
        clamped.scale = this.clampMaxScale(scale);
        
        // Depending on the relative aspect ratios of the canvas and image, we may need
        // to set the minScale value differently.
        if (this.ctx.canvas.width/this.ctx.canvas.height <= this.img.width/this.img.height) {
            // When zoomed out, letterboxed on top and bottom
            minScale = this.ctx.canvas.width;
            if (scale < minScale) clamped.scale = minScale;
            if (clamped.scale*this.img.height/this.img.width <= this.ctx.canvas.height) {
                // Letterboxing.
                maxY = minY = (this.ctx.canvas.height - clamped.scale*this.img.height/this.img.width)/2;
            }
            else {
                maxY = 0;
                minY = this.ctx.canvas.height - clamped.scale*this.img.height/this.img.width;
            }
            maxX = 0;
            minX = this.ctx.canvas.width - clamped.scale;
        }
        else {
            // When zoomed out, letterboxed on left and right.
            minScale = this.ctx.canvas.height * this.img.width/this.img.height;
            if (scale < minScale) clamped.scale = minScale;
            if (clamped.scale <= this.ctx.canvas.width) {
                // Letterboxing.
                maxX = minX = (this.ctx.canvas.width - clamped.scale)/2;
            }
            else {
                maxX = 0;
                minX = this.ctx.canvas.width - clamped.scale;
            }
            maxY = 0;
            minY = this.ctx.canvas.height - clamped.scale*this.img.height/this.img.width;
        }

        if (x > maxX && !this.is_panorama) clamped.x = maxX;
        if (x < minX && !this.is_panorama) clamped.x = minX;
        if (y > maxY) clamped.y = maxY;
        if (y < minY) clamped.y = minY;
        return clamped;
    },

    //------------------------------------------------------------------------------
    
    fmod: function(a,b) {
        return Number((a - (Math.floor(a / b) * b)).toPrecision(8));
    },

    //------------------------------------------------------------------------------
    // Clamp the translation of our box to make sure it doesn't leave the image region.
    clampBoxPosition: function(box) {
        // For panoramas, allow wrap-around in the x direction.
        if (this.is_panorama) {
            box.x = this.fmod(box.x, 1.0);
        }
        else {
            // Not panorama. Clamp to edge.
            if (box.x < 0.0) {
                box.x = 0.0;
            }
            if (box.x + box.width > 1.0) {
                box.x = 1.0-box.width;
            }
        }

        // Clamp to top and bottom.
        if (box.y < 0.0) {
            box.y = 0.0;
        }
        if (box.y + box.height > this.img.height/this.img.width) {
            box.y = this.img.height/this.img.width-box.height;
        }
    },

    //------------------------------------------------------------------------------
    // Clamp the scale of our box to make sure it doesn't leave the image region.
    clampBoxSize: function(box) {
        if (box.width < this.min_box_size) {
            box.width = this.min_box_size;
        }
        if (box.x + box.width > 1.0 && !this.is_panorama) {
            box.width = 1.0 - box.x;
        }
        if (box.height < this.min_box_size) {
            box.height = this.min_box_size;
        }
        if (box.y + box.height > this.img.height/this.img.width) {
            box.height = this.img.height/this.img.width-box.y;
        }
        if (box.width > this.max_box_size) {
            box.width = this.max_box_size;
        }
        if (box.height > this.max_box_size) {
            box.height = this.max_box_size;
        }
    },

    //------------------------------------------------------------------------------
    // We don't want to allow our scale factor to take us more than 1 texel per pixel
    // in the high-res image.
    clampMaxScale: function(scale) {
        var maxScale = 1920.0;
        if (this.is_panorama) {
            maxScale = 5120.0;
        }
        if (scale > maxScale) return maxScale;
        return scale;
    },

    //------------------------------------------------------------------------------
    redrawCanvas:function (clamp) {
        // Fill background.
        this.ctx.fillStyle = "#404040";
        this.ctx.fillRect(0,0,this.ctx.canvas.width, this.ctx.canvas.height);

        // Don't draw anything until the image is loaded.
        if (!this.img.is_loaded) {
            return;
        }

        var x, y;
        if (this.selectedBox == -1) {
            x = this.imgX + this.dx + this.dxPinch;
            y = this.imgY + this.dy + this.dyPinch;
        }
        else {
            x = this.imgX + this.dxPinch;
            y = this.imgY + this.dyPinch;
        }
        var scale = this.imgScale * this.dscale;
        var clamped = ce4.boxTagger.clampImage(x, y, scale);

        // If we could benefit from the high-res image, start loading it now.
        if (this.imgHighRes.src === "" && this.highResSrc !== undefined && this.texelsPerPixel(clamped.scale) > 1.0) {
            this.imgHighRes.src = this.highResSrc;
        }

        // Normally, we just draw everything once, but for panoramas, we draw 3x to span the seam.
        var drawCopies = 1;
        if (this.is_panorama) drawCopies = 3;
        for (var copy=0; copy<drawCopies; copy++) {
            var offset = 0;
            if (copy == 1) offset = clamped.scale;
            if (copy == 2) offset = -clamped.scale;

            if (this.showing_infrared && this.imgInfrared.is_loaded) {
                this.ctx.drawImage(this.imgInfrared, offset + clamped.x, clamped.y, clamped.scale, clamped.scale*this.img.height/this.img.width);
            }
            else if (!this.showing_infrared && this.img.is_loaded) {
                var imgBest = this.img;
                if (this.texelsPerPixel(clamped.scale) > 1.0 && this.imgHighRes.is_loaded) {
                    imgBest = this.imgHighRes;
                }
                this.ctx.drawImage(imgBest, offset + clamped.x, clamped.y, clamped.scale, clamped.scale*imgBest.height/imgBest.width);
            }

            // Debug: Show a label with the current offset index.
            //this.ctx.fillStyle = "#ffffff";
            //this.ctx.font = "100px Arial";
            //this.ctx.textAlign="center"; 
            //this.ctx.fillText(""+copy, offset + clamped.x+clamped.scale/2, clamped.y+100);
        }

        // Draw boxes.    
        for (var copy=0; copy<drawCopies; copy++) {
            var offset = 0;
            if (copy == 1) offset = clamped.scale;
            if (copy == 2) offset = -clamped.scale

            for (var b=0; b<this.boxes.length; b++) {
                var box = this.boxes[b];
                var screenCoord0 = this.imageToScreen(box.x, box.y, clamped.x, clamped.y, clamped.scale);
                var screenCoord1 = this.imageToScreen(box.x+box.width, box.y+box.height, clamped.x, clamped.y, clamped.scale);
                
                var boxColor = "#ffffff";
                if (b == this.selectedBox) {
                    boxColor = "#ffff80";
                    if (this.boxAction == this.BOX_ACTION_DRAG) {
                        // Dragging box. Translate x and y.
                        var newBox = {'x':box.x + this.dx/this.imgScale, 'y':box.y + this.dy/this.imgScale, 'width':box.width, 'height':box.height};
                        this.clampBoxPosition(newBox);
                        screenCoord0 = this.imageToScreen(newBox.x, newBox.y, clamped.x, clamped.y, clamped.scale);
                        screenCoord1 = this.imageToScreen(newBox.x+newBox.width, newBox.y+newBox.height, clamped.x, clamped.y, clamped.scale);
                    }
                    else {
                        // Resizing box. Change width and height.
                        var newBox = {'x':box.x, 'y':box.y, 'width':box.width + this.dx/this.imgScale, 'height':box.height + this.dy/this.imgScale};
                        this.clampBoxSize(newBox);
                        screenCoord0 = this.imageToScreen(newBox.x, newBox.y, clamped.x, clamped.y, clamped.scale);
                        screenCoord1 = this.imageToScreen(newBox.x+newBox.width, newBox.y+newBox.height, clamped.x, clamped.y, clamped.scale);
                    }
                }
                
                // Draw the box.
                this.ctx.beginPath();
                    this.ctx.lineWidth="1";
                    this.ctx.setLineDash([5, 3]);
                    this.ctx.strokeStyle=boxColor;
                    this.ctx.rect(Math.floor(offset + screenCoord0.x), Math.floor(screenCoord0.y), Math.floor(screenCoord1.x-screenCoord0.x), Math.floor(screenCoord1.y-screenCoord0.y));
                this.ctx.stroke();

                if (!box.is_locked) {
                    // Draw the close and resize icons.
                    this.ctx.globalAlpha = 0.75;
                    this.ctx.drawImage(this.iconClose, 0, 0, 88, 88, Math.floor(offset+screenCoord1.x-this.ICON_SIZE/2), Math.floor(screenCoord0.y-this.ICON_SIZE/2), this.ICON_SIZE, this.ICON_SIZE);
                    var iconY = 0;
                    if (b == this.selectedBox && this.boxAction == this.BOX_ACTION_RESIZE) {
                        iconY = 88;  // Highlighted version.
                    }
                    this.ctx.drawImage(this.iconResize, 0, iconY, 88, 88, Math.floor(offset+screenCoord1.x-this.ICON_SIZE/2), Math.floor(screenCoord1.y-this.ICON_SIZE/2), this.ICON_SIZE, this.ICON_SIZE);
                    this.ctx.globalAlpha = 1.0;
                }
                else {
                    // Draw labels
                    this.ctx.fillStyle = "#ffffff";
                    this.ctx.font = "14px Arial";
                    this.ctx.textAlign="center"; 
                    this.ctx.fillText(box.label, Math.floor(offset + 0.5*(screenCoord0.x+screenCoord1.x)), Math.floor(screenCoord0.y-6));
                }
            }
        }

        this.drawCompass(clamped.x, clamped.y, clamped.scale);
    }, 

    //------------------------------------------------------------------------------
    drawCompass: function(imgX, imgY, imgScale) {
        // Compute the homogeneous image coordinates [0,1] of the left and right edges of the current view.
        var imgLeft  = this.screenToImage(0.0, 0.0, imgX, imgY, imgScale).x;
        var imgRight = this.screenToImage(this.ctx.canvas.width, 0.0, imgX, imgY, imgScale).x;

        // Width of the visible region, in degrees.
        var imgDegrees = 90.0;
        if (this.is_panorama) {
            imgDegrees = 360.0;
        }

        // Convert the image coordinates into a compass (degrees).
        var compassLeft = this.yaw*180.0/Math.PI - imgDegrees/2.0 + imgLeft*imgDegrees;
        // Clamp to be between 0 and 360.
        while (compassLeft > 360.0) compassLeft -= 360.0;
        while (compassLeft < 0.0) compassLeft += 360.0;
        
        // Find the first multiple of 5 degrees that's visible on the left edge.
        var imgDeltaDegrees= (imgRight - imgLeft)*imgDegrees;
        var tickValue = Math.floor((compassLeft + 5.0)/5.0) * 5;
        var tickPosition = (tickValue-compassLeft)/imgDeltaDegrees * this.ctx.canvas.width;
        var tickIntervalScreen = this.ctx.canvas.width / (imgDeltaDegrees/5.0);
        var labelIntervalDegrees = 15;
        if (tickIntervalScreen < 15.0) {
            labelIntervalDegrees = 30;
        }
        
        // Set drawing parameters
        this.ctx.restore();
        this.ctx.setLineDash([0,0]);
        this.ctx.strokeStyle="#FFFFFF";
        this.ctx.lineWidth="1";
        this.ctx.fillStyle = "#ffffff";
        this.ctx.font = "14px Arial";
        this.ctx.textAlign="center"; 
        
        // Draw tick marks.
        while (tickPosition < this.ctx.canvas.width) {
            // For non-panorama images, don't draw compass ticks beyond the image edges.
            var x = this.screenToImage(tickPosition, 0.0, imgX, imgY, imgScale).x;
            if (this.is_panorama || (x >= 0.0 && x <= 1.0)) {
                if (tickValue >= 360) {
                    tickValue -= 360;
                }

                var strDir = '';
                if (tickValue == 0)   strDir = 'N';
                if (tickValue == 45)  strDir = 'NE';
                if (tickValue == 90)  strDir = 'E';
                if (tickValue == 135) strDir = 'SE';
                if (tickValue == 180) strDir = 'S';
                if (tickValue == 225) strDir = 'SW';
                if (tickValue == 270) strDir = 'W';
                if (tickValue == 315) strDir = 'NW';

                if (strDir == '') {
                    this.ctx.beginPath();
                    this.ctx.moveTo(tickPosition,0);
                    this.ctx.lineTo(tickPosition,8);
                    this.ctx.stroke();
                }
                else {
                    this.ctx.fillText(strDir, tickPosition, 12);
                }

                // Labels every 15 or 30 degrees.
                if (tickValue % labelIntervalDegrees == 0) {
                    this.ctx.fillText(''+tickValue+String.fromCharCode(176), tickPosition, 24);
                }
            }
            tickValue += 5;
            tickPosition += tickIntervalScreen;
        }
    },

    //------------------------------------------------------------------------------
    addBox: function() {
        // Limit the number of boxes.
        if (this.boxes.length >= 3)
            return;

        // What is the current center of the screen in image coordinates?
        var center = this.screenToImage(this.ctx.canvas.width/2, this.ctx.canvas.height/2, this.imgX, this.imgY, this.imgScale);

        // Center our new box on the screen.
        var newBox = {'x':center.x-this.min_box_size, 'y':center.y-this.min_box_size, 'width':this.min_box_size*2.0, 'height':this.min_box_size*2.0, 'is_locked':false, 'label':''};
        this.clampBoxPosition(newBox);
        this.boxes.push(newBox);
        this.redrawCanvas();

        // Trigger callback.
        ce4.boxTagger.cbTagChange();
    },
    removeBox: function(index) {
        this.boxes.splice(index, 1);
        if (ce4.boxTagger.cbCancelSelection !== undefined) {
            ce4.boxTagger.cbCancelSelection();
        }
    },
    addLabeledBox: function(x, y, width, height, label) {
        // Create a new box with a label. Transform our y height values into a different coordinate space.
        this.boxes.push({'x':x, 'y':y/this.aspect, 'width':width, 'height':height/this.aspect, 'is_locked':true, 'label':label});
        this.redrawCanvas();  

        // Trigger callback.
        ce4.boxTagger.cbTagChange();
    },
    submit: function() {
        for (var b=0; b<this.boxes.length; b++) {
            var box = this.boxes[b];
            box.is_locked = true;
            box.label = 'Pending';
        }
        this.redrawCanvas();
    },
    // Return the list of selections as normalized bounding boxes in this form:
    // [{'xmin':0, 'ymin':0, 'xmax':0, 'ymax':0},...]
    getSelectionList: function() {
        var result = new Array();
        for (var b=0; b<this.boxes.length; b++) {
            var box = this.boxes[b];
            if (!box.is_locked) {
                result.push({'xmin':box.x, 'ymin':box.y*this.aspect, 'xmax':box.x+box.width, 'ymax':(box.y+box.height)*this.aspect});
            }
        }
        return result;
    },
    imageToScreen: function(x, y, imgX, imgY, imgScale) {
        return {'x':imgX + imgScale*x, 'y':imgY + imgScale*y};
    },
    screenToImage: function(x, y, imgX, imgY, imgScale) {
        return {'x': (x - imgX)/imgScale, 'y': (y - imgY)/imgScale};
    },
    // Compute the ratio of texels to pixels for our low-res image. If greater than 1.0, we should use the high-res image.
    texelsPerPixel: function(imgScale) {
        if (this.is_panorama) {
            return imgScale/2400.0;
        }
        return imgScale/800.0;
    },
    toggleInfrared: function(src) {
        this.showing_infrared = !this.showing_infrared;

        // If the image we want to show is already loaded, trigger our callback to hide the loading icon.
        if (this.showing_infrared && this.imgInfrared.is_loaded) {
            this.cbHideLoader();
        }
        else if (!this.showing_infrared && this.img.is_loaded) {
            this.cbHideLoader();
        }
        // If we haven't yet started loading our infrared image, set the src now.
        else if (this.imgInfrared.src === "") {
            this.imgInfrared.src = src;
        }
        
        this.redrawCanvas();
    }
}

//------------------------------------------------------------------------------