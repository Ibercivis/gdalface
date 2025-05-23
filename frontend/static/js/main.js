$(document).ready(function () {
    // Function to parse the coordinate string and convert to decimal degrees
    function parseCoordinates(coordString) {
        // Updated regex to handle negative values and optional N/S, E/W indicators
        const regex = /([-+]?[0-9.]+)\s*([NS])?,?\s*([-+]?[0-9.]+)\s*([EW])?/;
        const matches = coordString.match(regex);
    
        if (matches) {
            let lat = parseFloat(matches[1]);
            let lng = parseFloat(matches[3]);
    
            // Adjust latitude based on N/S if present
            if (matches[2] === 'S') lat = -lat;
    
            // Adjust longitude based on E/W if present
            if (matches[4] === 'W') lng = -lng;
    
            return [lat, lng];  // Return the parsed latitude and longitude
        } else {
            console.error(`Invalid coordinate format: ${coordString}`);
            throw new Error("Invalid coordinate format");
        }
    }

    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }
    let iconCounter = 1; // Counter for numbering icons
    let iconList = []; // List to store icon objects
    let markerList = {}; // List to store marker objects
    let iconMap = {}; // List to store the iconGroup objects
    let isTurn = 'image'; // Variable to track the current turn
    let group; // Variable to store the Fabric group object
    let geoatempt_id; // Variable to store the geoattempt id
    let image_name; // Variable to store the image name
    let geoattempt_hash; // Variable to store the geoattempt hash
    let map; // Variable to store the Leaflet map object
    var baseLayers = null; // Variable to store the base layers
    let icon;
    var layersControl = null;
    let lyr;
    let opacityControl;
    let infoModal;
    let georeferencingModal;
    let viirs;
    let sdgsatEuUk; // Nueva variable para la capa SDGSAT_EU_UK
    infoModal = new bootstrap.Modal(document.getElementById('infoModal'), {
        keyboard: true // Allows closing the modal with the Esc key
    });
    georeferencingModal = new bootstrap.Modal(document.getElementById('georeferencingModal'), {
    });
    $('#usage-info').on('click', function () {
        console.log('clicked');
        $('.modal-title').html('Usage Information'); // Set the modal content
        $('.modal-body').html(
            'To georeference the image, please add at least three control points by clicking on the photography '
            +'and then on the map.<br/><br />The control points should be added in the correct order.<br /><br />'
            +'After adding the control points, click on the "Try" button to start the georeferencing process.<br /><br />'
            +'If your georeferenciation is correct, click on the "Submit" button to submit the control points.<br /><br />'  
            +'If you make a mistake, you can delete control points on the right bar.<br /><br />'
            +'You can drag (left mouse button) and rotate (right mouse button) the photography for your convenience'); // Set the modal body content
        infoModal.show(); // Show the modal
    }); 
    
     
    const csrftoken = getCookie('csrftoken');
    $.ajaxSetup({
        headers: {
            'X-CSRFToken': csrftoken
        }
    });
    url = '/api/v1/geoattempt-pending/';
    if ($('#batch-id').val() != null) {
        url = '/api/v1/geoattempt-pending/' + $('#batch-id').val() + '/';
    }
    $.ajax({
        url: url,
        type: 'GET',
        dataType: 'json',
        success: function (response) {
            image_name = response.image_name;
            geoatempt_id = response.id;
            geoattempt_hash = response.hash;
            
            // Eliminar la extensión JPG del nombre de la imagen para el texto informativo
            let displayImageName = image_name;
            displayImageName = displayImageName.replace(/\.JPG$|\.jpg$/, '');
            $('#photo-info-text').text(displayImageName);

            // Initialize Fabric.js canvas
            const canvas = new fabric.Canvas('canvas', {
                fireRightClick: true, // Enable right-click events
                stopContextMenu: true, // Disable the default context menu
                selection: false // Disable object selection
            });
            $('#photo-info-text').text(displayImageName);
           

            $('#photo-info').on('click', function () {
                // Format date if it's in ISO format
                let formattedDate = response.photo_taken || "Not provided";
                if (formattedDate && formattedDate.includes('T')) {
                    // Parse ISO date string
                    const date = new Date(response.photo_taken);
                    // Format the date as "YYYY-MM-DD HH:MM:SS" in English format
                    const year = date.getFullYear();
                    const month = String(date.getMonth() + 1).padStart(2, '0');
                    const day = String(date.getDate()).padStart(2, '0');
                    const hours = String(date.getHours()).padStart(2, '0');
                    const minutes = String(date.getMinutes()).padStart(2, '0');
                    const seconds = String(date.getSeconds()).padStart(2, '0');
                    formattedDate = `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
                }
                
                // Handle null values for all fields
                const photoCenterPoint = response.photo_center_point || "Not provided";
                const photoCenterByML = response.photo_center_by_machine_learning || "Not provided";
                const spacecraftNadirPoint = response.spacecraft_nadir_point || "Not provided";
                const focalLength = response.focal_length || "Not provided";
                
                // Eliminar la extensión JPG del nombre de la imagen para el título
                let imageTitle = response.image_name || "Untitled Image";
                imageTitle = imageTitle.replace(/\.JPG$|\.jpg$/, '');
                
                $('.modal-title').html(imageTitle); // Set the modal content with image name without JPG extension
                $('.modal-body').html(''
                    +'Photography Date: ' + formattedDate + '<br />'
                    +'Photography Center: ' + photoCenterPoint + '<br />'
                    +'Photography Center by Machine Learning: ' + photoCenterByML + '<br />'
                    +'ISS Position (Spacecraft Nadir Point): ' + spacecraftNadirPoint + '<br />'
                    +'Focal length: ' + focalLength + '<br />');
                infoModal.show(); // Show the modal
            });

            // Add buttons behavior
            $('#Try').on('click', function () {
                if (iconList.length < 3) {

                    $('.modal-title').html('Few control points!'); // Set the modal content
                    $('.modal-body').html('Please add at least three control points.'); // Set the modal body content
                    infoModal.show(); // Show the modal
                    return;
                } else {
                    $('.modal-title').html('Georefencing in progress...'); // Set the modal content
                    $('.modal-body').html('We are georeferencing the photography. Please wait.<br /><br />'
                        +'<div class="d-flex justify-content-center"><img width="40px" src="/static/img/doing.gif" /></div>'); // Set the modal body content
                    georeferencingModal.show();
                    // Doing a post request to the backend
                    const data = {
                        "geoattempt_id": geoatempt_id,
                        "control_points": iconList,
                        "status": "ASSIGNED"
                    }
                    $.ajax({
                        url: '/api/v1/geoattempt-individual/' + geoatempt_id + '/',
                        type: 'PATCH',
                        dataType: 'json',
                        headers: {
                            'X-CSRFToken': csrftoken,
                            'Content-Type': 'application/json'
                        },
                        data: JSON.stringify(data),

                        success: function (response) {
                            console.log(response);
                            georeferencingModal.hide();
                            let noCacheUrl = '/media/georeferenced/' + image_name + geoattempt_hash + '/{z}/{x}/{y}.png' + '?nocache=' + new Date().getTime();
                            if (lyr)
                                map.removeLayer(lyr);

                            lyr = L.tileLayer(noCacheUrl, {
                                tms: 1,
                                opacity: 0.9,
                                format: 'image/png',
                            }).addTo(map);

                            // Eliminar controles existentes
                            if (layersControl) {
                                map.removeControl(layersControl);
                            }
                            if (opacityControl) {
                                map.removeControl(opacityControl);
                            }
                            
                            // Definir capas base y superposiciones - necesitamos recrear las capas base
                            const osmLayerSuccess = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                                maxZoom: 18,
                                attribution: '© OpenStreetMap contributors'
                            });
                            
                            const mapBoxSuccess = L.tileLayer('https://api.mapbox.com/styles/v1/frasanz/cm2cctm8400u501pbb8tvgom7/tiles/256/{z}/{x}/{y}?access_token=pk.eyJ1IjoiZnJhc2FueiIsImEiOiJjbTF4bHE2MHIwdzRmMmpxd3g1cGZkbjR3In0.6B49yUgKNVhYOCy7ibw5ww', {
                                maxZoom: 18,
                                tileSize: 256,
                                attribution: '&copy; <a href="https://www.mapbox.com/about/maps/">Mapbox</a> &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                            });

                            const googleSatSuccess = L.tileLayer('http://{s}.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', {
                                maxZoom: 18,
                                subdomains: ['mt0', 'mt1', 'mt2', 'mt3'],
                                transparent: true,
                            });
                            
                            // Definir capas base y superposiciones
                            baseLayers = {
                                "OpenStreetMap": osmLayerSuccess,
                                "MapBox": mapBoxSuccess,
                                "Satellite": googleSatSuccess
                            };
                            
                            var overlaymaps = {
                                "VIIRS": viirs,
                                "SDGSAT EU/UK": sdgsatEuUk,
                                "Georeferenced": lyr
                            };
                            
                            // Crear un nuevo control de capas estándar
                            layersControl = L.control.layers(baseLayers, overlaymaps, { 
                                collapsed: false 
                            }).addTo(map);
                            
                            // Agregar el control deslizante dentro de la caja de control de capas
                            setTimeout(function() {
                                // Buscar todas las etiquetas en el control de capas
                                var layerControlElement = document.querySelector('.leaflet-control-layers');
                                if (!layerControlElement) return;
                                
                                var labels = layerControlElement.querySelectorAll('.leaflet-control-layers-overlays label');
                                
                                // Procesar todas las etiquetas para añadir sliders de opacidad
                                for (var i = 0; i < labels.length; i++) {
                                    var label = labels[i];
                                    var spanElement = label.querySelector('span');
                                    
                                    if (spanElement) {
                                        var text = spanElement.textContent.trim();
                                        var sliderContainer = document.createElement('div');
                                        sliderContainer.className = 'opacity-slider-inline';
                                        sliderContainer.style.display = 'inline-block';
                                        sliderContainer.style.marginLeft = '10px';
                                        sliderContainer.style.verticalAlign = 'middle';
                                        
                                        var slider = document.createElement('input');
                                        slider.type = 'range';
                                        slider.min = '0';
                                        slider.max = '1';
                                        slider.step = '0.05';
                                        slider.style.width = '80px';
                                        slider.style.verticalAlign = 'middle';
                                        
                                        // Configurar valor inicial y capa objetivo según el nombre
                                        if (text === 'VIIRS') {
                                            slider.value = '0.8'; // Valor inicial de VIIRS es 0.8
                                            slider.setAttribute('data-layer', 'viirs');
                                        } else if (text === 'SDGSAT EU/UK') {
                                            slider.value = '0.8'; // Valor inicial de SDGSAT es 0.8
                                            slider.setAttribute('data-layer', 'sdgsat');
                                        } else if (text === 'Georeferenced') {
                                            slider.value = '0.9'; // Valor inicial de Georeferenced es 0.9
                                            slider.setAttribute('data-layer', 'georeferenced');
                                        }
                                        
                                        // Añadir el slider al contenedor
                                        sliderContainer.appendChild(slider);
                                        
                                        // Añadir el contenedor después del texto
                                        spanElement.appendChild(sliderContainer);
                                        
                                        // Configurar el evento para cambiar la opacidad
                                        slider.addEventListener('input', function() {
                                            var layerType = this.getAttribute('data-layer');
                                            var opacityValue = parseFloat(this.value);
                                            
                                            if (layerType === 'viirs') {
                                                viirs.setOpacity(opacityValue);
                                            } else if (layerType === 'sdgsat') {
                                                sdgsatEuUk.setOpacity(opacityValue);
                                            } else if (layerType === 'georeferenced') {
                                                lyr.setOpacity(opacityValue);
                                            }
                                        });
                                        
                                        // Evitar que al hacer clic en el slider se active/desactive la capa
                                        slider.addEventListener('click', function(e) {
                                            e.stopPropagation();
                                        });
                                        
                                        // Ajustar el estilo del label para que tenga más espacio
                                        label.style.display = 'flex';
                                        label.style.alignItems = 'center';
                                        label.style.width = '100%';
                                    }
                                }
                            }, 100);
                            
                            // Ajustar zoom
                            var currentZoom = map.getZoom();
                            map.setZoom(11);
                            setTimeout(function () {
                                map.setZoom(response.maxZoom);
                            }, 300);  // Adjust the delay if necessary, 300ms works in most cases
                            $('#Submit').removeClass('disabled');

                        },
                        error: function (response) {
                            console.log(response);
                            georeferencingModal.hide();
                            $('.modal-title').html('Error!'); // Set the modal content
                            $('.modal-body').html('An error ' + response.status + ' occurred:<br />' + response.responseText); // Set the modal body content
                            infoModal.show(); // Show the modal
                        }
                    })
                }
            });

            $('#Submit').on('click', function () {
                // Doing a post request to the backend
                const data = {
                    "geoattempt_id": geoatempt_id,
                    "controlPoints": iconList,
                    "status": "DONE"
                }
                $.ajax({
                    url: '/api/v1/geoattempt-individual/' + geoatempt_id + '/',
                    type: 'PATCH',
                    dataType: 'json',
                    headers: {
                        'X-CSRFToken': csrftoken,
                        'Content-Type': 'application/json'
                    },
                    data: JSON.stringify(data),
                    success: function (response) {
                        console.log(response);
                        console.log('Control points submitted successfully');
                        $('.modal-title').html('Thank you for your contribution'); // Set the modal content
                        $('.modal-body').html('Your control points have been submitted successfully.'); // Set the modal body content
                        $('#modalClose').html('Try another one!');
                        $('#modalClose').on('click', function () {
                            location.reload();
                            $('#modalClose').html('Close');
                        });
                        infoModal.show(); // Show the modal

                    },
                    error: function (response) {
                        $('.modal-title').html('Error!'); // Set the modal content
                        $('.modal-body').html('An error ' + response.status + ' occurred:<br />' + response.responseText); // Set the modal body content
                        infoModal.show(); // Show the modal
                    }
                })
            });
            $('#Skip').on('click', function () {
                // Reload page
                // We release the task
                $.ajax({
                    url: '/api/v1/geoattempt-individual/' + geoatempt_id + '/',
                    type: 'PATCH',
                    dataType: 'json',
                    headers: {
                        'X-CSRFToken': csrftoken,
                        'Content-Type': 'application/json'
                    },
                    data: JSON.stringify({ "status": "PENDING" }),
                    success: function (response) {
                        location.reload();
                    },
                    error: function (response) {
                        $('.modal-title').html('Error!'); // Set the modal content
                        $('.modal-body').html('An error ' + response.status + ' occurred:<br />' + response.responseText); // Set the modal body content
                        infoModal.show(); // Show the modal
                    }
                });
            });
            const static_url = "/media/original/"; // Static URL
            const imageUrl = static_url + image_name; // Image URL
            console.log(response);
            let latLng = "";
            const canvasWidth = $('#column-photo').width(); // Canvas width
            const canvasHeight = $('#column-photo').height(); // Canvas height
            canvas.setWidth(canvasWidth); // Set the canvas width
            canvas.setHeight(canvasHeight); // Set the canvas height
            canvas.hoverCursor = 'default'; // Set the cursor style

            // Load an image into the Fabric canvas
            fabric.Image.fromURL(imageUrl, function (img) {
                const scaleX = canvasWidth / img.width;
                const scaleY = canvasHeight / img.height;
                const scale = Math.min(scaleX, scaleY);
                const originalIconScale = 1.05; // Original scale for icons
                let isRightClickDragging = false; // Flag to track right-click drag state
                let isDragging = false; // Flag to track left-click drag state
                let isDragged = false; // Flag to track if the image was dragged
                let startX; // Initial X position for rotation calculation
                let isPKeyActive = false;
                let isDKeyActive = false;
                let lastPosX; // Last X position for drag movement
                let lastPosY; // Last Y position for drag movement
                img.set({
                    left: 0, // Center horizontally
                    top: 0, // Center vertically
                    originX: 'left',
                    originY: 'top',
                    scaleX: scale,
                    scaleY: scale,
                    selectable: false, // Make the image non-selectable to avoid default transformations
                    hasControls: false, // Disable controls for the image
                    hasBorders: false, // Disable borders for the image
                });
                group = new fabric.Group([img], {
                    left: canvasWidth / 2,
                    top: canvasHeight / 2,
                    originX: 'center',
                    originY: 'center',
                    selectable: false, // Make the group non-selectable
                    hasControls: false, // Disable controls for the group
                    hasBorders: false, // Disable borders for the group
                });
                canvas.add(group);
                document.addEventListener('keydown', function (event) {
                    if (event.key === 'p' || event.key === 'P') {
                        isPKeyActive = true;
                    }
                });
                // Track the "p" key release
                document.addEventListener('keyup', function (e) {
                    if (e.key === 'p' || e.key === 'P') {
                        isPKeyActive = false;
                    }
                });
                document.addEventListener('keydown', function (event) {
                    if (event.key === 'd' || event.key === 'D') {
                        isDKeyActive = true;
                    }
                });
                document.addEventListener('keyup', function (e) {
                    if (e.key === 'd' || e.key === 'D') {
                        isDKeyActive = false;
                        document.body.style.cursor = 'default';
                    }
                });

                function addIcon(iconURL, event) {
                    fabric.Image.fromURL(iconURL, function (icon) {
                        const pointer = canvas.getPointer(event.e);
                        const x = pointer.x;
                        const y = pointer.y;

                        const label = new fabric.Text('\uf3c5', {
                            left: x,
                            top: y, // Position the label above the icon
                            fontSize: 16,
                            fontFamily: 'Font Awesome 6 Free',
                            fill: '#e9f900',
                            originX: 'center',
                            originY: 'center',
                            selectable: false,  // Make the label non-selectable
                            hasControls: false, // Disable controls for the label
                            hasBorders: false,   // Disable borders for the label
                            stroke: '#000000',
                            strokeWidth: 1,
                        });

                        const label1Text = new fabric.Text(iconCounter.toString(), {
                            fontSize: 12,
                            fontFamily: 'Open Sans',
                            fill: '#e9f900',
                            originX: 'center',
                            originY: 'center',
                            selectable: false,
                            hasControls: false,
                            hasBorders: false
                        });
                        
                        const label1Background = new fabric.Rect({
                            fill: 'black',
                            width: label1Text.width + 5,  // Add padding to the background
                            height: label1Text.height + 5, // Add padding to the background
                            originX: 'center',
                            originY: 'center',
                            rx: 5,  // Set the border radius to make it rounded
                            ry: 5
                        });
                        
                        // Group the text and background
                        const label1Group = new fabric.Group([label1Background, label1Text], {
                            left: x,
                            top: y - 14,
                            originX: 'center',
                            originY: 'center',
                            selectable: false,
                            hasControls: false,
                            hasBorders: false
                        });

                        // Create a unique ID for the icon
                        const iconID = `Point ${iconCounter}`;

                        const iconGroup = new fabric.Group([label1Group, label], {
                            id: iconID,
                            left: x,
                            top: y,
                            originX: 'center',
                            originY: 'bottom',
                            selectable: true,  // Make the group selectable
                            hasControls: false, // Disable controls for the group
                            hasBorders: false   // Disable borders for the group
                        });

                        // Store the icon object in the list
                        iconList.push({
                            id: iconID,
                            px: iconGroup.left,
                            py: iconGroup.top,
                            text: getImageCoordinates(event),
                            actualPx: getImageCoordinates(event).px,
                            actualPy: getImageCoordinates(event).py
                        });

                        // Add the iconGroup to the iconMap by ID
                        iconMap[iconID] = iconGroup;
                        console.log(iconList);

                        updateIconList(); // Update the icon list displayed in the div
                        group.addWithUpdate(iconGroup); // Add the icon to the group
                        canvas.requestRenderAll(); // Re-render the canvas
                    }, { crossOrigin: 'anonymous' }); // Handle CORS issues
                }

                function deleteNearestIconGroup(px, py) {
                    let closestIconGroup = null;
                    let closestDistance = Infinity;

                    // Iterate over all objects in the group to find the closest one
                    group.getObjects().forEach(function (obj) {
                        if (obj !== img) { // Exclude the main image
                            const dx = obj.left - px;
                            const dy = obj.top - py;
                            const distance = Math.sqrt(dx * dx + dy * dy);

                            if (distance < closestDistance) {
                                closestDistance = distance;
                                closestIconGroup = obj;
                            }
                        }
                    });

                    // Remove the closest icon group if found
                    if (closestIconGroup) {
                        removeMarkerPointById(closestIconGroup.id);
                        canvas.requestRenderAll(); // Re-render the canvas
                    }
                }

                function removeIconById(id) {
                    const iconGroup = iconMap[id];
                    if (iconGroup) {
                        group.remove(iconGroup); // Remove the icon from the group
                        delete iconMap[id]; // Remove the icon from the map
                        canvas.requestRenderAll(); // Re-render the canvas
                    } else {
                        console.log(`Icon ${id} not found.`);
                    }
                }

                function removeMarkerById(id) {
                    if (markerList[id]) {
                        map.removeLayer(markerList[id].marker); // Remove the marker from the map
                        delete markerList[id]; // Remove the marker from the list
                    }
                }



                function removeIconFromList(id) {
                    iconList = iconList.filter(icon => icon.id !== id); // Remove the icon from the list
                }

                function removeMarkerPointById(id) {
                    icon = iconList.find(icon => icon.id === id);
                    console.log(icon);
                    if (icon.complete && isTurn === 'map') {
                        isTurn = 'map';
                    }
                    else if (!icon.complete && isTurn === 'map') {
                        isTurn = 'image';
                    }
                    removeMarkerById(id);
                    removeIconById(id);
                    removeIconFromList(id);
                    updateIconList();
                    console.log(iconList);
                }

                // Function to update the icon list in the div
                function updateIconList() {
                    const listContainer = document.getElementById('icon-list-items');
                    listContainer.innerHTML = ''; // Clear the current list



                    // Create list items for each icon in iconList
                    iconList.forEach(function (icon) {
                        const listItem = document.createElement('li');
                        listItem.id = "li-" + icon.id; // Set the ID attribute
                        console.log(icon.complete);

                        // Create Font Awesome icon element
                        const iconElement = document.createElement('i');
                        iconElement.className = 'fa-solid fa-location-dot ps-2 pe-2'; // Add the classes for the Font Awesome icon
                        
                        // Check if it is complete and add class to li
                        if (icon.complete) {
                            listItem.classList.add('completed');
                        }
                        // Set the text content with the ID, X, and Y values
                        const span = document.createElement('span');
                        span.textContent = `${icon.id}`;
                        const spanRight = document.createElement('span');
                        spanRight.className = 'float-end d-block';
                        const info = document.createElement('span');
                        info.className = 'fa-solid fa-info-circle pe-3 white';
                        info.setAttribute('data-bs-toggle', 'tooltip');
                        info.setAttribute('data-bs-placement', 'right');
                        info.setAttribute('title', `px: ${icon.text.px.toFixed(2)} <br /> py: ${icon.text.py.toFixed(2)} <br> lat: ${icon.text.lat} <br> lon: ${icon.text.lon}`); // Set the tooltip text

                        const garbage = document.createElement('i');
                        garbage.className = 'fa-solid fa-trash-alt pe-2 white'

                        // If garbage icon is clicked, remove the icon
                        garbage.addEventListener('click', function () {
                            removeMarkerPointById(icon.id);
                        });

                        // Append the icon and the text to the list item
                        listItem.appendChild(iconElement);
                        listItem.appendChild(span);
                        listItem.appendChild(spanRight);
                        spanRight.appendChild(info);
                        spanRight.appendChild(garbage);

                        // Append the list item to the container
                        listContainer.appendChild(listItem);

                        // Scroll the coordinates div to the bottom
                        

                    });
                    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
                    const tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
                        return new bootstrap.Tooltip(tooltipTriggerEl, {
                            html: true, // Enable HTML content in the tooltip
                            delay: { show: 100, hide: 100 }, // Adjust the show/hide delay in milliseconds

                        });
                    });
                    $('#coordinates').scrollTop($('#coordinates')[0].scrollHeight);
                }



                // Function to convert canvas click coordinates to image coordinates
                function getImageCoordinates(event) {
                    // Get the pointer position on the canvas
                    const pointer = canvas.getPointer(event.e);

                    // Create a point from the click position
                    const clickPoint = new fabric.Point(pointer.x, pointer.y);

                    // Get the inverse transform matrix of the group
                    const inverseGroupMatrix = fabric.util.invertTransform(img.calcTransformMatrix());

                    // Transform the click point to the image's local coordinates
                    const transformedPoint = fabric.util.transformPoint(clickPoint, inverseGroupMatrix);

                    return { px: transformedPoint.x + img.width / 2, py: transformedPoint.y + img.height / 2 };
                }

                if(response.photo_center_point){
                    latLng = parseCoordinates(response.photo_center_point);
                } else if (response.photo_center_by_machine_learning) {
                    latLng = parseCoordinates(response.photo_center_by_machine_learning);
                } else {
                    latLng = parseCoordinates(response.spacecraft_nadir_point);
                }



                viirs = L.tileLayer('https://lostatnight.org/viirs_tiles/{z}/{x}/{y}.png', {
                    //viirs = L.tileLayer('https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/VIIRS_Black_Marble/default/2016-01-01/GoogleMapsCompatible_Level8/{z}/{x}/{y}.png', {   
                    //viirs = L.tileLayer('https://earthengine.googleapis.com/v1/projects/ee-pmisson/maps/7f05e1c56c7139d418df9f275abae720-880cdb032adeb5dabd4855934e8d1764/tiles/{z}/{x}/{y}', { 
                    //viirs = L.tileLayer('https://earthengine.googleapis.com/v1/projects/ee-pmisson/maps/7f05e1c56c7139d418df9f275abae720-880cdb032adeb5dabd4855934e8d1764/tiles/{z}/{x}/{y}', {
                    maxZoom: 18,
                    maxNativeZoom: 12,
                    transparent: true,
                    tms: 1,
                    attribution: 'The Earth Observation Group (EOG)',
                    opacity: 0.8,
                });

                // Añadir la nueva capa SDGSAT_EU_UK
                sdgsatEuUk = L.tileLayer('https://lostatnight.org/tileset/SDGSAT_EU_UK/{z}/{x}/{y}.png', {
                    maxZoom: 18,
                    maxNativeZoom: 13,
                    transparent: true,
                    tms: 1,
                    attribution: 'SDGSAT @ LostAtNight.org',
                    opacity: 0.8,
                });

                const osmLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                    maxZoom: 18,
                    attribution: '© OpenStreetMap contributors'
                });

                //const mapBox = L.tileLayer('https://api.mapbox.com/styles/v1/frasanz/cm2cdt26700t301pghdcsc7b0/tiles/256/{z}/{x}/{y}?access_token=pk.eyJ1IjoiZnJhc2FueiIsImEiOiJjbTF4bHE2MHIwdzRmMmpxd3g1cGZkbjR3In0.6B49yUgKNVhYOCy7ibw5ww', {
                //const mapBox = L.tileLayer('https://api.mapbox.com/styles/v1/germangil/cm2x26xaf00ns01qw9jooe6w/tiles/256/{z}/{x}/{y}?access_token=pk.eyJ1IjoiZ2VybWFuZ2lsIiwiYSI6ImNsbXQxbDBoNTAwbjkybGxvcngxNDBhYzgifQ.kcRn3hE1wUpA1KpdxiG23g',{ 
                const mapBox = L.tileLayer('https://api.mapbox.com/styles/v1/frasanz/cm2cctm8400u501pbb8tvgom7/tiles/256/{z}/{x}/{y}?access_token=pk.eyJ1IjoiZnJhc2FueiIsImEiOiJjbTF4bHE2MHIwdzRmMmpxd3g1cGZkbjR3In0.6B49yUgKNVhYOCy7ibw5ww', {
                    maxZoom: 18,
                    tileSize: 256,
                    attribution: '&copy; <a href="https://www.mapbox.com/about/maps/">Mapbox</a> &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                });

                const googleSat = L.tileLayer('http://{s}.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', {
                    maxZoom: 18,
                    subdomains: ['mt0', 'mt1', 'mt2', 'mt3'],
                    transparent: true,
                });
                map = L.map('map', { layers: [viirs],  maxZoom: 18 }).setView(latLng, 10);
                osmLayer.addTo(map);
                console.log("Here");
                console.log(map.getZoom());
                map.on('zoom', function() {
                    console.log("Zoom level changed:", map.getZoom());
                    // zoombox update
                    document.getElementById('zoombox').innerHTML = 'Zoom level: ' + map.getZoom();
                });
           

                // Add layer control to switch between layers
                baseLayers = {
                    "OpenStreetMap": osmLayer,
                    "MapBox": mapBox,
                    "Satellite": googleSat
                };
                var overlaymaps = { 
                    "VIIRS": viirs,
                    "SDGSAT EU/UK": sdgsatEuUk
                }

                // Crear un control personalizado para mostrar "hola" debajo de los botones de zoom
                L.Control.HelloMessage = L.Control.extend({
                    onAdd: function(map) {
                        var div = L.DomUtil.create('div', 'hello-message-control');
                        div.innerHTML = '<div id="zoombox" style="background-color: white; padding: 5px; border-radius: 4px; box-shadow: 0 1px 5px rgba(0,0,0,0.4); margin: 15px; text-align: center;"></div>';
                        return div;
                    },
                    
                    onRemove: function(map) {
                        // Nada que hacer aquí
                    }
                });
                
                // Añadir el control personalizado al mapa, en la misma posición que los controles de zoom
                L.control.helloMessage = function(opts) {
                    return new L.Control.HelloMessage(opts);
                }
                
                L.control.helloMessage({ position: 'bottomleft' }).addTo(map);

                layersControl = L.control.layers(baseLayers, overlaymaps, { collapsed: false }).addTo(map);

                // Añadir sliders de opacidad para VIIRS y SDGSAT desde el inicio
                setTimeout(function() {
                    // Buscar todas las etiquetas en el control de capas
                    var layerControlElement = document.querySelector('.leaflet-control-layers');
                    if (!layerControlElement) return;
                    
                    var labels = layerControlElement.querySelectorAll('.leaflet-control-layers-overlays label');
                    
                    // Procesar las etiquetas para añadir sliders de opacidad
                    for (var i = 0; i < labels.length; i++) {
                        var label = labels[i];
                        var spanElement = label.querySelector('span');
                        
                        if (spanElement) {
                            var text = spanElement.textContent.trim();
                            if (text === 'VIIRS' || text === 'SDGSAT EU/UK') {
                                var sliderContainer = document.createElement('div');
                                sliderContainer.className = 'opacity-slider-inline';
                                sliderContainer.style.display = 'inline-block';
                                sliderContainer.style.marginLeft = '10px';
                                sliderContainer.style.verticalAlign = 'middle';
                                
                                var slider = document.createElement('input');
                                slider.type = 'range';
                                slider.min = '0';
                                slider.max = '1';
                                slider.step = '0.05';
                                slider.style.width = '80px';
                                slider.style.verticalAlign = 'middle';
                                
                                // Configurar valor inicial y capa objetivo según el nombre
                                if (text === 'VIIRS') {
                                    slider.value = '0.8';
                                    slider.setAttribute('data-layer', 'viirs');
                                } else if (text === 'SDGSAT EU/UK') {
                                    slider.value = '0.8';
                                    slider.setAttribute('data-layer', 'sdgsat');
                                }
                                
                                // Añadir el slider al contenedor
                                sliderContainer.appendChild(slider);
                                
                                // Añadir el contenedor después del texto
                                spanElement.appendChild(sliderContainer);
                                
                                // Configurar el evento para cambiar la opacidad
                                slider.addEventListener('input', function() {
                                    var layerType = this.getAttribute('data-layer');
                                    var opacityValue = parseFloat(this.value);
                                    
                                    if (layerType === 'viirs') {
                                        viirs.setOpacity(opacityValue);
                                    } else if (layerType === 'sdgsat') {
                                        sdgsatEuUk.setOpacity(opacityValue);
                                    }
                                });
                                
                                // Evitar que al hacer clic en el slider se active/desactive la capa
                                slider.addEventListener('click', function(e) {
                                    e.stopPropagation();
                                });
                                
                                // Ajustar el estilo del label
                                label.style.display = 'flex';
                                label.style.alignItems = 'center';
                                label.style.width = '100%';
                            }
                        }
                    }
                }, 100);

                function addIconToMap(lat, lon) {
                    // Create a custom icon using Leaflet's divIcon and Font Awesome
                    var icon = L.divIcon({
                        id: `Point ${iconCounter}`, // Unique ID for the icon
                        className: 'fa-icon-marker', // Use custom class to style the icon
                        html: `<div class="map-icon"><span class="black">${iconCounter}</span><i class="fa-solid fa-location-dot"></i></div>`, // Font Awesome icon
                        iconSize: [20, 24], // Set the icon size to match the font size
                        iconAnchor: [10, 30], // Center the bottom of the icon at the clicked point
                        popupAnchor: [0, -20] // Optional: Position of the popup relative to the icon
                    });

                    // Add the icon as a marker to the map
                    var marker = L.marker([lat, lon], { icon: icon }).addTo(map);
                    markerList[`Point ${iconCounter}`] = {
                        marker,
                        lat,
                        lon
                    }; // Store the marker object
                    // Get the last icon object from the list

                    iconList[iconList.length - 1].lat = lat; // Store the icon's coordinates
                    iconList[iconList.length - 1].lon = lon;
                    iconList[iconList.length - 1].text.lat = lat;
                    iconList[iconList.length - 1].text.lon = lon;
                    iconList[iconList.length - 1].complete = true;
                    console.log(iconList);
                    updateIconList(); // Update the icon list displayed in the div
                    iconCounter++; // Increment the icon counter
                }




                map.on('click', function (e) {
                    if (isTurn === 'image') {

                        $('.modal-title').html('Wrong place!'); // Set the modal content
                        $('.modal-body').html('Please add the control point on the image first.'); // Set the modal body content
                        infoModal.show(); // Show the modal
                        return;
                    } else {
                        var lat = e.latlng.lat;
                        var lon = e.latlng.lng;
                        addIconToMap(lat, lon); // Add icon to the clicked location
                        isTurn = 'image'; // Switch back to image turn
                    }
                });


                canvas.on('mouse:wheel', function (event) {
                    const delta = -event.e.deltaY; // Get the scroll direction
                    const zoomFactor = 300;
                
                    // Calculate the new zoom level
                    let zoom = group.scaleX + delta / zoomFactor; // Adjust the zoom factor
                    zoom = Math.max(0.1, Math.min(zoom, 10)); // Set a minimum and maximum zoom level (adjust to your needs)
                
                    // Get the mouse position relative to the canvas before zooming
                    const pointer = canvas.getPointer(event.e);
                
                    // Calculate the position of the mouse relative to the group's current position
                    const prevZoomPointX = (pointer.x - group.left) / group.scaleX;
                    const prevZoomPointY = (pointer.y - group.top) / group.scaleY;
                
                    // Apply the zoom to the group
                    group.scaleX = zoom;
                    group.scaleY = zoom;
                
                    // After zooming, recalculate the group's position so that the point under the mouse stays in the same place
                    group.left = pointer.x - prevZoomPointX * zoom;
                    group.top = pointer.y - prevZoomPointY * zoom;
                
                    // Adjust any other objects' scale inside the group (like icons)
                    group.getObjects().forEach(function (obj) {
                        if (obj !== img) { // Exclude the main image
                            obj.scaleX = originalIconScale / group.scaleX;
                            obj.scaleY = originalIconScale / group.scaleY;
                        }
                    });
                
                    // Re-render the canvas
                    canvas.requestRenderAll();
                
                    // Prevent default scrolling behavior
                    event.e.preventDefault();
                    event.e.stopPropagation();
                });

                // Event for mouse down
                canvas.on('mouse:down', function (event) {
                    if (event.e.button === 0) { // Left mouse button (button === 0)
                        if (isPKeyActive) {


                        } else if (isDKeyActive) {
                            const pointer = canvas.getPointer(event.e);
                            const px = pointer.x;
                            const py = pointer.y;
                            deleteNearestIconGroup(px, py);

                        } else {
                            isDragging = true;
                            lastPosX = event.e.clientX;
                            lastPosY = event.e.clientY;
                            event.e.preventDefault();
                        }
                    }


                    // alert(event.e.button);
                    else if (event.e.button === 2) { // Right-click (button === 2)
                        isRightClickDragging = true;
                        startX = event.e.clientX; // Store initial X position
                        event.e.preventDefault(); // Prevent default context menu
                    }
                });

                // Event for mouse move
                canvas.on('mouse:move', function (event) {
                    /* Check tha move is greatest than 5 pixels */
                    if (Math.abs(event.e.movementX) > 5 || Math.abs(event.e.movementY) > 5) {
                        if (isDragging) {
                            isDragged = true;
                            const currentPosX = event.e.clientX;
                            const currentPosY = event.e.clientY;

                            // Calculate the difference in X and Y positions
                            const deltaX = currentPosX - lastPosX;
                            const deltaY = currentPosY - lastPosY;

                            // Update the image position based on the mouse movement
                            group.left += deltaX;
                            group.top += deltaY;

                            // Update the last position for continuous movement
                            lastPosX = currentPosX;
                            lastPosY = currentPosY;
                            canvas.hoverCursor = 'grabbing'; // Change the cursor style

                            canvas.requestRenderAll(); // Re-render the canvas with the new position

                        } else if (isRightClickDragging) {
                            const currentX = event.e.clientX; // Get current X position
                            const deltaX = currentX - startX; // Calculate the difference in X

                            // Adjust the rotation angle based on the mouse movement
                            group.rotate(group.angle - deltaX * 0.2); // Adjust the multiplier for sensitivity
                            canvas.requestRenderAll(); // Re-render the canvas with the new rotation

                            // Update the start position for continuous rotation
                            startX = currentX;
                            canvas.hoverCursor = 'grabbing'; // Change the cursor style
                        } else {

                        }

                    }

                });

                // Event for mouse up
                canvas.on('mouse:up', function (event) {
                    // Check which mouse button was released
            
                    if (event.e.button === 0) { // Left mouse button
                        canvas.hoverCursor = 'default'; // Change the cursor style
                      

                        // If we don't drag the image, add an icon
                        if (!isDragged) {
                            console.log(isTurn);
                            console.log(isDragging);
                            console.log(isDragged);

                            if (isTurn === 'image') {

                                // Get the pointer position on the canvas
                                const pointer = canvas.getPointer(event.e);
                                const px = pointer.x;
                                const py = pointer.y;

                                // Add an icon at the click position
                                addIcon("{% static 'images/maps-and-flags.png' %}", event); // Example icon URL
                                isTurn = 'map'; // Switch to map turn
                                isDragging = false; // Stop the left-click drag movement
                                isDragged = false; // Reset the drag state
                            } else {
                                console.log('Wrong place!');
                                $('.modal-title').html('Wrong place!'); // Set the modal content
                                $('.modal-body').html('Please add a point in the map (related to the last control point).'); // Set the modal body content
                            
                                infoModal.show(); // Show the modal

                                isDragging = false; // Stop the left-click drag movement
                                isDragged = false; // Reset the drag state
                                
                                return;
                            }

                        }
                        isDragging = false; // Stop the left-click drag movement
                        isDragged = false; // Reset the drag state


                    } else if (event.e.button === 2) { // Right mouse button

                        isRightClickDragging = false; // Stop the right-click drag rotation
                        canvas.hoverCursor = 'default'; // Change the cursor style
                    }
                });
            });
        },
        error: function (response) {
            console.log(response);
            $('.modal-title').html('Error!'); // Set the modal content
            $('.modal-body').html('An error ' + response.status + ' occurred:<br />' + response.responseText); // Set the modal body content
                // Add a button to go to /batch url
                $('.modal-footer').html('<button type="button" class="btn btn-primary" id="go-to-batch">Go to batchs </button>');
                $('#go-to-batch').on('click', function () {
                    window.location.href = '/batchs';
                }
                );
            infoModal.show(); // Show the modal
        }

    });
});
