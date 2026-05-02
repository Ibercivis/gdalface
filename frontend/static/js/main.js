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
    let lyr;
    let opacityControl;
    let infoModal;
    let georeferencingModal;
    let viirs;
    let sdgsatEuUk; // Nueva variable para la capa SDGSAT_EU_UK
    infoModal = new bootstrap.Modal(document.getElementById('taskInfoModal'), {
        keyboard: true // Allows closing the modal with the Esc key
    });
    georeferencingModal = new bootstrap.Modal(document.getElementById('georeferencingModal'), {
    });

    // Public namespace for trylocal.js
    window.LAN = {
        get iconList() { return iconList; },
        get map()      { return map; },
        infoModal: infoModal,
        georeferencingModal: georeferencingModal,
        currentMapFilter: '',
        geoLayer: null,
        tryLocalLayer: null,
        applyMapFilters: function() {
            var f = window.LAN.currentMapFilter;
            var tl = window.LAN.tryLocalLayer;
            var gl = window.LAN.geoLayer;
            if (tl && tl._image) tl._image.style.filter = f;
            if (gl && gl._container) gl._container.style.filter = f;
        },
    };
    $('#usage-info').on('click', function () {
        georeferencingModal.hide();
        infoModal.show();
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
            var opacitySlidersDiv = null;
            var makeSliderRow = null;

            // Eliminar la extensión JPG del nombre de la imagen para el texto informativo
            let displayImageName = image_name;
            displayImageName = displayImageName.replace(/\.JPG$|\.jpg$/, '');
            $('#photo-info-text').text(displayImageName);

            // --- Task Info Modal ---
            (function showTaskInfoModal() {

                $('#ti-image').text(displayImageName);

                // Date — slice ISO string directly to avoid timezone shift
                let formattedDate = response.photo_taken
                    ? response.photo_taken.substring(0, 10)
                    : 'Unknown';
                $('#ti-date').text(formattedDate);

                // Focal length
                $('#ti-focal').text(response.focal_length || 'Unknown');

                // Coordinates
                const fmtCoord = c => c ? c : '—';
                $('#ti-nadir').text(fmtCoord(response.spacecraft_nadir_point));
                $('#ti-photo-center').text(fmtCoord(response.photo_center_point));
                if (response.photo_center_by_machine_learning) {
                    $('#ti-ml-center').text(response.photo_center_by_machine_learning);
                    $('#ti-ml-row').show();
                } else {
                    $('#ti-ml-row').hide();
                }

                // Expedition & crew
                if (response.expedition_number) {
                    $('#ti-exp-number').text(response.expedition_number);
                    const crewList = $('#ti-crew-list').empty();
                    const crew = response.crew || [];
                    if (crew.length === 0) {
                        crewList.append($('<span class="text-muted">').text('Crew data not available'));
                    } else {
                        crew.forEach(function(member) {
                            const name = typeof member === 'object' ? member.name : member;
                            const imgUrl = typeof member === 'object' ? member.image_url : '';
                            const wikiUrl = typeof member === 'object' ? member.wikipedia_url : '';
                            const card = $('<div class="text-center" style="width:70px">');
                            const inner = wikiUrl
                                ? $('<a>').attr({href: wikiUrl, target: '_blank', title: name}).css({color: 'inherit', textDecoration: 'none'})
                                : $('<span>').attr('title', name);
                            if (imgUrl) {
                                inner.append($('<img>').attr({src: imgUrl, alt: name})
                                    .addClass('rounded-circle mb-1 d-block mx-auto')
                                    .css({width:'52px', height:'52px', objectFit:'cover'}));
                            }
                            inner.append($('<div class="small lh-sm">').text(name.split(' ').pop()));
                            card.append(inner);
                            crewList.append(card);
                        });
                    }
                } else {
                    $('#ti-crew-col').hide();
                }

                // User stats
                if (response.user_stats) {
                    const s = response.user_stats;
                    const fmt = (rank, val) => rank === 1 ? '🥇' : val;
                    const fmtRank = r => r ? '#' + r : '—';

                    $('#ti-stat-tasks').text(s.tasks_done);
                    $('#ti-stat-tasks-rank').text(fmtRank(s.tasks_rank));
                    $('#ti-stat-tasks-next').text(fmt(s.tasks_rank, s.tasks_to_next));
                    $('#ti-stat-tasks-first').text(fmt(s.tasks_rank, s.tasks_to_first));

                    $('#ti-stat-cp').text(s.control_points);
                    $('#ti-stat-cp-rank').text(fmtRank(s.cp_rank));
                    $('#ti-stat-cp-next').text(fmt(s.cp_rank, s.cp_to_next));
                    $('#ti-stat-cp-first').text(fmt(s.cp_rank, s.cp_to_first));

                    $('#ti-stat-hours').text(s.hours + 'h');
                    $('#ti-stat-hours-rank').text(fmtRank(s.time_rank));
                    $('#ti-stat-hours-next').text(fmt(s.time_rank, s.time_to_next + 'h'));
                    $('#ti-stat-hours-first').text(fmt(s.time_rank, s.time_to_first + 'h'));

                    $('#ti-stats-section').removeClass('d-none');
                }

                // Reverse geocode photoCenterPoint via Nominatim
                const coords = response.photo_center_point || response.spacecraft_nadir_point;
                if (coords) {
                    const parts = coords.split(',');
                    const lat = parseFloat(parts[0]);
                    const lon = parseFloat(parts[1]);
                    if (!isNaN(lat) && !isNaN(lon)) {
                        fetch(`https://nominatim.openstreetmap.org/reverse?lat=${lat}&lon=${lon}&format=json`, {
                            headers: {'Accept-Language': 'en'}
                        })
                        .then(r => r.json())
                        .then(geo => {
                            const addr = geo.address || {};
                            const city = addr.city || addr.town || addr.village || addr.county || '';
                            const country = addr.country || '';
                            $('#ti-location').text([city, country].filter(Boolean).join(', ') || 'Open ocean / unknown');
                        })
                        .catch(() => $('#ti-location').text('Could not determine'));
                    } else {
                        $('#ti-location').text('Not available');
                    }
                } else {
                    $('#ti-location').text('Not available');
                }

                infoModal.show();
            })();
            // --- End Task Info Modal ---

            // Initialize Fabric.js canvas
            const canvas = new fabric.Canvas('canvas', {
                fireRightClick: true, // Enable right-click events
                stopContextMenu: true, // Disable the default context menu
                selection: false // Disable object selection
            });
            $('#photo-info-text').text(displayImageName);
           

            $('#photo-info').on('click', function () {
                infoModal.show();
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
                            window.LAN.geoLayer = lyr;
                            window.LAN.applyMapFilters();

                            // Add/replace Georeferenced slider (always recreate so it binds to the new lyr)
                            if (opacitySlidersDiv) {
                                var existing = document.getElementById('georef-slider-row');
                                if (existing) existing.remove();
                                opacitySlidersDiv.appendChild(makeSliderRow('Georeferenced', lyr, 0.9, 'georef-slider-row'));
                            }

                            // Ajustar zoom
                            map.setZoom(response.maxZoom);
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
                        if (typeof window.LAN_refreshChallenge === 'function') {
                            window.LAN_refreshChallenge();
                        }
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
            window.LAN.imageUrl = imageUrl;
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
                let startAngle; // Initial angle (radians) from group center to mouse, for rotation
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
                    objectCaching: false,
                });
                canvas.add(group);

                // Image filters (brightness, contrast, gamma, saturation)
                // Force 2D backend to avoid WebGL dimension issues with images inside groups
                fabric.filterBackend = new fabric.Canvas2dFilterBackend();

                var brightnessFilter  = new fabric.Image.filters.Brightness({ brightness: 0 });
                var contrastFilter    = new fabric.Image.filters.Contrast({ contrast: 0 });
                var gammaFilter       = new fabric.Image.filters.Gamma({ gamma: [1, 1, 1] });
                var saturationFilter  = new fabric.Image.filters.Saturation({ saturation: 0 });
                img.filters = [brightnessFilter, contrastFilter, gammaFilter, saturationFilter];

                function applyImageFilters() {
                    img.applyFilters();
                    group.dirty = true;
                    canvas.requestRenderAll();
                    // Apply equivalent CSS filters to the map layers
                    var b = brightnessFilter.brightness;   // -1 to 1
                    var c = contrastFilter.contrast;       // -1 to 1
                    var s = saturationFilter.saturation;   // -1 to 1
                    window.LAN.currentMapFilter =
                        'brightness(' + Math.max(0, 1 + b).toFixed(3) + ') ' +
                        'contrast('   + Math.max(0, 1 + c).toFixed(3) + ') ' +
                        'saturate('   + Math.max(0, 1 + s).toFixed(3) + ')';
                    window.LAN.applyMapFilters();
                }

                document.getElementById('brightness-slider').addEventListener('input', function() {
                    brightnessFilter.brightness = parseFloat(this.value);
                    document.getElementById('brightness-val').textContent = this.value;
                    applyImageFilters();
                });
                document.getElementById('contrast-slider').addEventListener('input', function() {
                    contrastFilter.contrast = parseFloat(this.value);
                    document.getElementById('contrast-val').textContent = this.value;
                    applyImageFilters();
                });
                document.getElementById('gamma-slider').addEventListener('input', function() {
                    var g = parseFloat(this.value);
                    gammaFilter.gamma = [g, g, g];
                    document.getElementById('gamma-val').textContent = this.value;
                    applyImageFilters();
                });
                document.getElementById('saturation-slider').addEventListener('input', function() {
                    saturationFilter.saturation = parseFloat(this.value);
                    document.getElementById('saturation-val').textContent = this.value;
                    applyImageFilters();
                });
                document.getElementById('reset-filters').addEventListener('click', function() {
                    document.getElementById('brightness-slider').value = 0;
                    document.getElementById('contrast-slider').value = 0;
                    document.getElementById('gamma-slider').value = 1;
                    document.getElementById('saturation-slider').value = 0;
                    document.getElementById('brightness-val').textContent = '0';
                    document.getElementById('contrast-val').textContent = '0';
                    document.getElementById('gamma-val').textContent = '1';
                    document.getElementById('saturation-val').textContent = '0';
                    brightnessFilter.brightness = 0;
                    contrastFilter.contrast = 0;
                    gammaFilter.gamma = [1, 1, 1];
                    saturationFilter.saturation = 0;
                    applyImageFilters();
                });

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
                            objectCaching: false,
                        });

                        const label1Text = new fabric.Text(iconCounter.toString(), {
                            fontSize: 12,
                            fontFamily: 'Open Sans',
                            fill: '#e9f900',
                            originX: 'center',
                            originY: 'center',
                            selectable: false,
                            hasControls: false,
                            hasBorders: false,
                            objectCaching: false,
                        });

                        const label1Background = new fabric.Rect({
                            fill: 'black',
                            width: label1Text.width + 5,  // Add padding to the background
                            height: label1Text.height + 5, // Add padding to the background
                            originX: 'center',
                            originY: 'center',
                            rx: 5,  // Set the border radius to make it rounded
                            ry: 5,
                            objectCaching: false,
                        });

                        // Group the text and background
                        const label1Group = new fabric.Group([label1Background, label1Text], {
                            left: x,
                            top: y - 14,
                            originX: 'center',
                            originY: 'center',
                            selectable: false,
                            hasControls: false,
                            hasBorders: false,
                            objectCaching: false,
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
                            hasBorders: false,  // Disable borders for the group
                            objectCaching: false,
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
                    className: 'sdgsat-tiles',
                });

                // Dynamic style element for SDGSAT CSS filters
                var sdgsatFilterStyle = document.createElement('style');
                sdgsatFilterStyle.id = 'sdgsat-filter-style';
                document.head.appendChild(sdgsatFilterStyle);
                var sdgsatFilters = { brightness: 1, contrast: 1, saturate: 1 };
                function applySdgsatFilters() {
                    var f = sdgsatFilters;
                    sdgsatFilterStyle.textContent = '.sdgsat-tiles { filter: brightness(' + f.brightness + ') contrast(' + f.contrast + ') saturate(' + f.saturate + '); }';
                }

                const osmLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                    maxZoom: 18,
                    attribution: '© OpenStreetMap contributors',
                    className: 'osm-tiles'
                });

                const googleSat = L.tileLayer('http://{s}.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', {
                    maxZoom: 18,
                    subdomains: ['mt0', 'mt1', 'mt2', 'mt3'],
                    transparent: true,
                });

                // VIIRS and SDGSAT are always on the map; visibility controlled by opacity sliders
                map = L.map('map', { maxZoom: 18, touchZoom: false, tap: false }).setView(latLng, 10);
                window.LAN.map = map;
                osmLayer.addTo(map);
                viirs.addTo(map);
                sdgsatEuUk.addTo(map);

                map.on('zoom', function() {
                    document.getElementById('zoombox').innerHTML = 'Zoom level: ' + map.getZoom();
                });
                map.getContainer().addEventListener('mousedown', function() {
                    map.scrollWheelZoom.disable();
                });
                document.addEventListener('mouseup', function() {
                    setTimeout(function() { map.scrollWheelZoom.enable(); }, 300);
                });


                baseLayers = {
                    "OpenStreetMap": osmLayer,
                    "Satellite": googleSat
                };

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

                // Custom control: base layer buttons + opacity sliders (no checkboxes)
                makeSliderRow = function(label, layer, initialOpacity, rowId) {
                    var row = document.createElement('div');
                    if (rowId) row.id = rowId;
                    row.style.cssText = 'display:flex;align-items:center;gap:8px;margin-bottom:4px;';
                    var lbl = document.createElement('span');
                    lbl.textContent = label;
                    lbl.style.minWidth = '90px';
                    var slider = document.createElement('input');
                    slider.type = 'range';
                    slider.min = '0';
                    slider.max = '1';
                    slider.step = '0.05';
                    slider.value = String(initialOpacity);
                    slider.style.width = '80px';
                    slider.addEventListener('input', function() {
                        layer.setOpacity(parseFloat(this.value));
                    });
                    L.DomEvent.disableClickPropagation(slider);
                    L.DomEvent.disableScrollPropagation(slider);
                    slider.addEventListener('mousedown', function(e) { e.stopPropagation(); });
                    slider.addEventListener('mouseup', function(e) { e.stopPropagation(); });
                    row.appendChild(lbl);
                    row.appendChild(slider);
                    return row;
                }

                L.Control.OpacitySliders = L.Control.extend({
                    onAdd: function() {
                        opacitySlidersDiv = L.DomUtil.create('div', 'leaflet-control-layers leaflet-control-layers-expanded');
                        opacitySlidersDiv.style.cssText = 'padding:6px 10px;font-size:13px;';
                        L.DomEvent.disableClickPropagation(opacitySlidersDiv);
                        L.DomEvent.disableScrollPropagation(opacitySlidersDiv);
                        window.LAN.opacitySlidersDiv = opacitySlidersDiv;
                        window.LAN.makeSliderRow = makeSliderRow;

                        // Base layer toggle buttons
                        var baseRow = document.createElement('div');
                        baseRow.style.cssText = 'display:flex;gap:4px;margin-bottom:6px;';
                        var activeLayer = osmLayer;
                        var btnStyle = 'font-size:11px;padding:2px 6px;border:1px solid #aaa;border-radius:3px;cursor:pointer;background:#fff;';
                        var btnActiveStyle = 'font-size:11px;padding:2px 6px;border:1px solid #555;border-radius:3px;cursor:pointer;background:#555;color:#fff;';
                        var btnOsm = document.createElement('button');
                        btnOsm.textContent = 'OSM';
                        btnOsm.style.cssText = btnActiveStyle;
                        var btnSat = document.createElement('button');
                        btnSat.textContent = 'Satellite';
                        btnSat.style.cssText = btnStyle;
                        function switchBase(newLayer, activeBtn, inactiveBtn) {
                            map.removeLayer(activeLayer);
                            newLayer.addTo(map);
                            newLayer.bringToBack();
                            activeLayer = newLayer;
                            activeBtn.style.cssText = btnActiveStyle;
                            inactiveBtn.style.cssText = btnStyle;
                        }
                        btnOsm.addEventListener('click', function() { switchBase(osmLayer, btnOsm, btnSat); });
                        btnSat.addEventListener('click', function() { switchBase(googleSat, btnSat, btnOsm); });
                        L.DomEvent.disableClickPropagation(btnOsm);
                        L.DomEvent.disableClickPropagation(btnSat);
                        baseRow.appendChild(btnOsm);
                        baseRow.appendChild(btnSat);
                        opacitySlidersDiv.appendChild(baseRow);

                        opacitySlidersDiv.appendChild(makeSliderRow('VIIRS', viirs, 0.8));
                        opacitySlidersDiv.appendChild(makeSliderRow('SDGSAT EU/UK', sdgsatEuUk, 0.8));

                        // SDGSAT image filters
                        var filterSep = document.createElement('div');
                        filterSep.style.cssText = 'border-top:1px solid #ccc;margin:4px 0 4px 0;font-size:11px;color:#666;';
                        filterSep.textContent = 'SDGSAT filters';
                        opacitySlidersDiv.appendChild(filterSep);

                        function makeSdgsatFilterRow(label, filterKey, min, max, step, initial) {
                            var row = document.createElement('div');
                            row.style.cssText = 'display:flex;align-items:center;gap:8px;margin-bottom:4px;';
                            var lbl = document.createElement('span');
                            lbl.textContent = label;
                            lbl.style.minWidth = '90px';
                            var slider = document.createElement('input');
                            slider.type = 'range';
                            slider.min = String(min);
                            slider.max = String(max);
                            slider.step = String(step);
                            slider.value = String(initial);
                            slider.style.width = '80px';
                            var val = document.createElement('span');
                            val.textContent = String(initial);
                            val.style.cssText = 'min-width:32px;text-align:right;';
                            slider.addEventListener('input', function() {
                                sdgsatFilters[filterKey] = parseFloat(this.value);
                                val.textContent = this.value;
                                applySdgsatFilters();
                            });
                            L.DomEvent.disableClickPropagation(slider);
                            L.DomEvent.disableScrollPropagation(slider);
                            slider.addEventListener('mousedown', function(e) { e.stopPropagation(); });
                            slider.addEventListener('mouseup', function(e) { e.stopPropagation(); });
                            row.appendChild(lbl);
                            row.appendChild(slider);
                            row.appendChild(val);
                            return row;
                        }

                        opacitySlidersDiv.appendChild(makeSdgsatFilterRow('Brightness', 'brightness', 0, 3, 0.05, 1));
                        opacitySlidersDiv.appendChild(makeSdgsatFilterRow('Contrast',   'contrast',   0, 3, 0.05, 1));
                        opacitySlidersDiv.appendChild(makeSdgsatFilterRow('Saturation', 'saturate',   0, 3, 0.05, 1));

                        var dynSep = document.createElement('div');
                        dynSep.id = 'dyn-layers-sep';
                        dynSep.style.cssText = 'border-top:1px solid #ccc;margin:6px 0 2px 0;';
                        opacitySlidersDiv.appendChild(dynSep);

                        return opacitySlidersDiv;
                    },
                    onRemove: function() {}
                });
                L.control.opacitySliders = function(opts) { return new L.Control.OpacitySliders(opts); };
                L.control.opacitySliders({ position: 'topright' }).addTo(map);

                function addIconToMap(lat, lon) {
                    var capturedID = `Point ${iconCounter}`; // capture before increment

                    // Create a custom icon using Leaflet's divIcon and Font Awesome
                    var icon = L.divIcon({
                        id: capturedID,
                        className: 'fa-icon-marker', // Use custom class to style the icon
                        html: `<div class="map-icon"><span class="black">${iconCounter}</span><i class="fa-solid fa-location-dot"></i></div>`, // Font Awesome icon
                        iconSize: [20, 24], // Set the icon size to match the font size
                        iconAnchor: [10, 30], // Center the bottom of the icon at the clicked point
                        popupAnchor: [0, -20] // Optional: Position of the popup relative to the icon
                    });

                    // Add the icon as a draggable marker to the map
                    var marker = L.marker([lat, lon], { icon: icon, draggable: true }).addTo(map);

                    marker.on('dragend', function() {
                        var ll = marker.getLatLng();
                        var entry = iconList.find(function(i) { return i.id === capturedID; });
                        if (entry) {
                            entry.lat = ll.lat;
                            entry.lon = ll.lng;
                            entry.text.lat = ll.lat;
                            entry.text.lon = ll.lng;
                        }
                        if (markerList[capturedID]) {
                            markerList[capturedID].lat = ll.lat;
                            markerList[capturedID].lon = ll.lng;
                        }
                        updateIconList();
                    });

                    markerList[capturedID] = { marker, lat, lon };

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
                        const pointer = canvas.getPointer(event.e);
                        startAngle = Math.atan2(pointer.y - group.top, pointer.x - group.left);
                        event.e.preventDefault(); // Prevent default context menu
                    }
                });

                // Event for mouse move
                canvas.on('mouse:move', function (event) {
                    if (isRightClickDragging) {
                        const pointer = canvas.getPointer(event.e);
                        const currentAngle = Math.atan2(pointer.y - group.top, pointer.x - group.left);
                        const deltaAngle = currentAngle - startAngle;
                        group.rotate(group.angle + deltaAngle * (180 / Math.PI));
                        canvas.requestRenderAll();
                        startAngle = currentAngle;
                        canvas.hoverCursor = 'grabbing';
                    } else if (Math.abs(event.e.movementX) > 5 || Math.abs(event.e.movementY) > 5) {
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
