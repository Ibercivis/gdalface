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
    let alertModal;
    let viirs;
    let sdgsatEuUk; // Nueva variable para la capa SDGSAT_EU_UK
    infoModal = new bootstrap.Modal(document.getElementById('taskInfoModal'), {
        keyboard: true // Allows closing the modal with the Esc key
    });
    georeferencingModal = new bootstrap.Modal(document.getElementById('georeferencingModal'), {
    });
    alertModal = new bootstrap.Modal(document.getElementById('alertModal'), {
        keyboard: true,
    });

    // Show an ephemeral alert in its own dedicated modal so it never
    // overwrites the structured contents of #taskInfoModal or
    // #georeferencingModal. `body` may contain HTML.
    function showAlert(title, body) {
        document.getElementById('alertModal-title').textContent = title;
        document.getElementById('alertModal-body').innerHTML = body;
        alertModal.show();
    }

    // Public namespace for trylocal.js — merge with anything already defined
    // (e.g. refreshPhotoTitle wired up by the inline template script that runs
    // before $(document).ready). We use defineProperty for the getters so they
    // stay live (Object.assign would invoke them once and freeze the value).
    window.LAN = window.LAN || {};
    Object.defineProperty(window.LAN, 'iconList', {
        configurable: true,
        enumerable: true,
        get: function () { return iconList; },
    });
    Object.defineProperty(window.LAN, 'map', {
        configurable: true,
        enumerable: true,
        get: function () { return map; },
    });
    window.LAN.infoModal           = infoModal;
    window.LAN.georeferencingModal = georeferencingModal;
    window.LAN.currentMapFilter    = '';
    window.LAN.geoLayer            = null;
    window.LAN.tryLocalLayer       = null;
    window.LAN.applyMapFilters = function () {
        var f = window.LAN.currentMapFilter;
        var tl = window.LAN.tryLocalLayer;
        var gl = window.LAN.geoLayer;
        if (tl && tl._image) tl._image.style.filter = f;
        if (gl && gl._container) gl._container.style.filter = f;
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
            if (window.LAN) {
                window.LAN.imageName = image_name.replace(/\.(jpe?g|png|tiff?)$/i, '');
                window.LAN.imageCaption = '';
            }
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
                    $('#ti-ml-row, #ti-ml-row-dt').show();
                } else {
                    $('#ti-ml-row, #ti-ml-row-dt').hide();
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
                            const label = [city, country].filter(Boolean).join(', ') || 'Open ocean / unknown';
                            $('#ti-location').text(label);
                            if (window.LAN) {
                                window.LAN.imageCaption = label;
                                if (typeof window.LAN.refreshPhotoTitle === 'function') {
                                    window.LAN.refreshPhotoTitle();
                                }
                            }
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
                    var T = window.LAN_I18N || {};
                    showAlert(T.few_cp_title || 'Few control points!',
                              T.few_cp_body || 'Please add at least three control points.');
                    return;
                } else {
                    $('#georeferencingModal .modal-title').html('Georeferencing in progress...');
                    $('#georeferencingModal .modal-body').html('We are georeferencing the photography. Please wait.<br /><br />'
                        +'<div class="d-flex justify-content-center"><img width="40px" src="/static/img/doing.gif" /></div>');
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

                            // Add/replace Georeferenced slider (always recreate so it binds to the new lyr).
                            // Insert at the dyn-layers anchor so it sits alongside VIIRS/SDGSAT layer
                            // opacities, above the image-filter sliders.
                            if (opacitySlidersDiv) {
                                var existing = document.getElementById('georef-slider-row');
                                if (existing) existing.remove();
                                var anchor = document.getElementById('dyn-layers-sep');
                                var row = makeSliderRow('Georeferenced', lyr, 0.9, 'georef-slider-row');
                                if (anchor) {
                                    opacitySlidersDiv.insertBefore(row, anchor);
                                } else {
                                    opacitySlidersDiv.appendChild(row);
                                }
                            }

                            // Ajustar zoom
                            map.setZoom(response.maxZoom);
                            $('#Submit').removeClass('disabled');

                        },
                        error: function (response) {
                            console.log(response);
                            georeferencingModal.hide();
                            var T = window.LAN_I18N || {};
                            showAlert(T.error_title || 'Error',
                                (T.error_generic || 'An error occurred.') + ' (' + response.status + ')<br />' + response.responseText);
                        }
                    })
                }
            });

            $('#Submit').on('click', function () {
                // Guard against double-clicks: a second PATCH would now be
                // refused by the server (409) and show an error.
                if ($(this).prop('disabled')) return;
                $(this).prop('disabled', true);
                // Doing a post request to the backend
                const data = {
                    "geoattempt_id": geoatempt_id,
                    "control_points": iconList,
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
                        if (typeof window.LAN_showResult === 'function') {
                            window.LAN_showResult({
                                cpCount: (iconList && iconList.length) || 0,
                                imageName: window.LAN && window.LAN.imageName,
                                imageCaption: window.LAN && window.LAN.imageCaption,
                                result: response && response.result,
                            });
                        } else {
                            // Fallback when the result UI script failed to load.
                            var T = window.LAN_I18N || {};
                            showAlert(T.thanks_title || 'Thank you for your contribution',
                                T.thanks_body || 'Your control points have been submitted successfully.');
                        }
                    },
                    error: function (response) {
                        $('#Submit').prop('disabled', false);
                        var T = window.LAN_I18N || {};
                        var body = {};
                        try { body = response.responseJSON || JSON.parse(response.responseText || '{}'); } catch (e) {}
                        showAlert(T.error_title || 'Error',
                            (body.error || (T.error_generic || 'An error occurred.')) + ' (' + response.status + ')');
                    }
                })
            });
            // Skip: ask why in one click (the reason performs the skip). The
            // answer is a crowd label for the photo; "no reason" is always offered.
            function doSkip(reason) {
                $.ajax({
                    url: '/api/v1/geoattempt-individual/' + geoatempt_id + '/',
                    type: 'PATCH',
                    dataType: 'json',
                    headers: {
                        'X-CSRFToken': csrftoken,
                        'Content-Type': 'application/json'
                    },
                    data: JSON.stringify({ "status": "PENDING", "skip_reason": reason || 'none' }),
                    success: function (response) {
                        location.reload();
                    },
                    error: function (response) {
                        var T = window.LAN_I18N || {};
                        showAlert(T.error_title || 'Error',
                            (T.error_generic || 'An error occurred.') + ' (' + response.status + ')<br />' + response.responseText);
                    }
                });
            }
            window.LAN_doSkip = doSkip;
            $('#Skip').on('click', function () {
                var T = window.LAN_I18N || {};
                var reasons = [
                    ['not_night', T.skip_not_night || 'Not a night photo'],
                    ['no_city',   T.skip_no_city   || 'No city lights visible'],
                    ['too_hard',  T.skip_too_hard  || 'Too hard to locate'],
                    ['bad_image', T.skip_bad_image || 'Problem with the image'],
                ];
                var html = '<p style="margin:0 0 12px;color:var(--ink-2);font-size:13px;">' + (T.skip_intro || 'Tell us why, it helps us pick better photos.') + '</p>'
                    + '<div style="display:grid;gap:8px;">'
                    + reasons.map(function (r) {
                        return '<button type="button" class="ds-btn ds-btn--secondary ds-btn--md" style="justify-content:flex-start" onclick="LAN_doSkip(\'' + r[0] + '\')">' + r[1] + '</button>';
                    }).join('')
                    + '<button type="button" class="ds-btn ds-btn--ghost ds-btn--md" onclick="LAN_doSkip(\'none\')">' + (T.skip_no_reason || 'Just skip') + '</button>'
                    + '</div>';
                showAlert(T.skip_title || 'Skip this photo', html);
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
                        // Set the text content with the ID, X, and Y values.
                        // Tooltip lives on the label itself (hover Point N to see coords).
                        const span = document.createElement('span');
                        span.textContent = `${icon.id}`;
                        span.setAttribute('data-bs-toggle', 'tooltip');
                        span.setAttribute('data-bs-placement', 'right');
                        var latStr = (typeof icon.text.lat === 'number') ? icon.text.lat.toFixed(4) : '—';
                        var lonStr = (typeof icon.text.lon === 'number') ? icon.text.lon.toFixed(4) : '—';
                        span.setAttribute('title',
                            '<div class="cp-tip-row"><span>px</span><b>' + Math.round(icon.text.px) + '</b></div>' +
                            '<div class="cp-tip-row"><span>py</span><b>' + Math.round(icon.text.py) + '</b></div>' +
                            '<div class="cp-tip-row"><span>lat</span><b>' + latStr + '</b></div>' +
                            '<div class="cp-tip-row"><span>lon</span><b>' + lonStr + '</b></div>'
                        );
                        span.style.cursor = 'help';
                        span.style.flex = '1';

                        const spanRight = document.createElement('span');
                        spanRight.className = 'float-end d-block';

                        const garbage = document.createElement('i');
                        garbage.className = 'fa-solid fa-trash-alt pe-2 white';
                        garbage.style.cursor = 'pointer';

                        // If garbage icon is clicked, remove the icon
                        garbage.addEventListener('click', function () {
                            removeMarkerPointById(icon.id);
                        });

                        // Append the icon and the text to the list item
                        listItem.appendChild(iconElement);
                        listItem.appendChild(span);
                        listItem.appendChild(spanRight);
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

                // Live photo coord readout (bottom-right of the canvas column).
                var photoCoordReadout = document.getElementById('ds-photo-coord');
                if (photoCoordReadout) {
                    canvas.on('mouse:move', function (event) {
                        try {
                            var c = getImageCoordinates(event);
                            if (c.px >= 0 && c.py >= 0 && c.px <= img.width && c.py <= img.height) {
                                photoCoordReadout.textContent = Math.round(c.px) + ', ' + Math.round(c.py) + ' px';
                            } else {
                                photoCoordReadout.textContent = '—';
                            }
                        } catch (e) { /* before img is ready */ }
                    });
                    canvas.on('mouse:out', function () { photoCoordReadout.textContent = '—'; });
                }


                if(response.photo_center_point){
                    latLng = parseCoordinates(response.photo_center_point);
                } else if (response.photo_center_by_machine_learning) {
                    latLng = parseCoordinates(response.photo_center_by_machine_learning);
                } else {
                    latLng = parseCoordinates(response.spacecraft_nadir_point);
                }



                viirs = L.tileLayer('https://lostatnight.org/viirs_tiles/{z}/{x}/{y}.png', {
                    maxZoom: 18,
                    maxNativeZoom: 12,
                    transparent: true,
                    tms: 1,
                    attribution: 'The Earth Observation Group (EOG)',
                    opacity: 0.8,
                    className: 'viirs-tiles',
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

                // Dynamic style element for SDGSAT + VIIRS CSS filters
                var sdgsatFilterStyle = document.createElement('style');
                sdgsatFilterStyle.id = 'sdgsat-filter-style';
                document.head.appendChild(sdgsatFilterStyle);
                // Slider scale 0..1 (consistent with the layer opacity sliders).
                // 0 = full attenuation, 0.5 = no effect (identity), 1 = max boost.
                // CSS filter intensity = slider * 2.
                var sdgsatFilters = { brightness: 0.5, contrast: 0.5, saturate: 0.5 };
                function applySdgsatFilters() {
                    var f = sdgsatFilters;
                    var rule = 'filter: brightness(' + (f.brightness * 2) + ') contrast(' + (f.contrast * 2) + ') saturate(' + (f.saturate * 2) + ');';
                    sdgsatFilterStyle.textContent = '.sdgsat-tiles, .viirs-tiles { ' + rule + ' }';
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
                map = L.map('map', { maxZoom: 18, touchZoom: false, tap: false, zoomControl: false }).setView(latLng, 10);
                window.LAN.map = map;
                window.LAN.fabric = canvas;
                osmLayer.addTo(map);
                viirs.addTo(map);
                sdgsatEuUk.addTo(map);

                // ISS nadir marker — hint showing where the station was directly
                // overhead when the photo was taken (spacecraft nadir point).
                try {
                var nadirCoord = response.spacecraft_nadir_point
                    ? parseCoordinates(response.spacecraft_nadir_point) : null;
                if (nadirCoord) {
                    // Real ISS silhouette (top-down), painted in the brand yellow
                    // via CSS mask so the SVG's own colours are ignored.
                    var issIcon = L.divIcon({
                        html: '<div style="width:42px;height:42px;background:var(--accent);' +
                            '-webkit-mask:url(/static/img/iss.svg) center/contain no-repeat;' +
                            'mask:url(/static/img/iss.svg) center/contain no-repeat;' +
                            'filter:drop-shadow(0 0 1.5px rgba(0,0,0,.9))"></div>',
                        className: 'iss-nadir-icon',
                        iconSize: [42, 42],
                        iconAnchor: [21, 21],
                    });
                    window.LAN.issMarker = L.marker(nadirCoord, {
                        icon: issIcon,
                        keyboard: false,
                        zIndexOffset: 1000,
                        title: 'ISS (nadir)',
                    }).addTo(map);
                    window.LAN.issMarker.bindTooltip('ISS (nadir)', { direction: 'top', offset: [0, -10] });
                }
                } catch (e) { /* malformed nadir coord — skip ISS marker, don't break the task */ }

                // Coord readout (design system, bottom-right of the map).
                var coordReadout = document.getElementById('ds-coord-readout');
                if (coordReadout) {
                    map.on('mousemove', function (e) {
                        coordReadout.textContent =
                            e.latlng.lat.toFixed(4) + ', ' + e.latlng.lng.toFixed(4);
                    });
                    map.on('mouseout', function () { coordReadout.textContent = '—'; });
                }
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

                // Custom control: base layer buttons + opacity sliders (no checkboxes)
                makeSliderRow = function(label, layer, initialOpacity, rowId) {
                    var row = document.createElement('div');
                    if (rowId) row.id = rowId;
                    row.style.cssText = 'display:flex;align-items:center;gap:8px;margin-bottom:2px;';
                    var lbl = document.createElement('span');
                    lbl.textContent = label;
                    lbl.style.minWidth = '70px';
                    var slider = document.createElement('input');
                    slider.type = 'range';
                    slider.min = '0';
                    slider.max = '1';
                    slider.step = '0.05';
                    slider.value = String(initialOpacity);
                    slider.style.flex = '1';
                    var val = document.createElement('span');
                    val.className = 'mono';
                    val.textContent = parseFloat(initialOpacity).toFixed(2);
                    val.style.cssText = 'min-width:28px;text-align:right;';
                    slider.addEventListener('input', function() {
                        var v = parseFloat(this.value);
                        layer.setOpacity(v);
                        val.textContent = v.toFixed(2);
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

                L.Control.OpacitySliders = L.Control.extend({
                    onAdd: function() {
                        var outer = L.DomUtil.create('div', 'leaflet-control-layers leaflet-control-layers-expanded ds-map-adjust');
                        outer.style.cssText = 'font-size:12px;';
                        L.DomEvent.disableClickPropagation(outer);
                        L.DomEvent.disableScrollPropagation(outer);

                        // Header
                        var header = document.createElement('div');
                        header.className = 'ds-map-adjust__head';
                        header.innerHTML =
                            '<span><svg class="ds-icon ds-icon--sm" viewBox="0 0 24 24" fill="none" ' +
                            'stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">' +
                            '<path d="M9 4l-6 2v14l6-2 6 2 6-2V4l-6 2-6-2z"/><path d="M9 4v16M15 6v16"/>' +
                            '</svg>Map adjustments</span>';
                        outer.appendChild(header);

                        // Body wrapper — subsequent appends use opacitySlidersDiv = body.
                        opacitySlidersDiv = document.createElement('div');
                        opacitySlidersDiv.className = 'ds-map-adjust__body';
                        outer.appendChild(opacitySlidersDiv);
                        window.LAN.opacitySlidersDiv = opacitySlidersDiv;
                        window.LAN.makeSliderRow = makeSliderRow;

                        // Base layer toggle buttons
                        var baseRow = document.createElement('div');
                        baseRow.className = 'ds-baselayer-row';
                        var activeLayer = osmLayer;
                        var btnOsm = document.createElement('button');
                        btnOsm.type = 'button';
                        btnOsm.textContent = 'OSM';
                        btnOsm.className = 'ds-baselayer-btn is-active';
                        var btnSat = document.createElement('button');
                        btnSat.type = 'button';
                        btnSat.textContent = 'Satellite';
                        btnSat.className = 'ds-baselayer-btn';
                        function switchBase(newLayer, activeBtn, inactiveBtn) {
                            map.removeLayer(activeLayer);
                            newLayer.addTo(map);
                            newLayer.bringToBack();
                            activeLayer = newLayer;
                            activeBtn.classList.add('is-active');
                            inactiveBtn.classList.remove('is-active');
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

                        // Anchor for dynamic layer sliders (e.g. Georeferenced)
                        // appended later — they get inserted *here*, so they sit
                        // alongside the other layer-opacity rows and above the
                        // SDGSAT/VIIRS image-filter sliders.
                        var dynSep = document.createElement('div');
                        dynSep.id = 'dyn-layers-sep';
                        opacitySlidersDiv.appendChild(dynSep);

                        // SDGSAT image filters
                        var filterSep = document.createElement('div');
                        filterSep.style.cssText = 'margin:6px 0 3px;font-size:10px;color:var(--ink-3);text-transform:uppercase;letter-spacing:1px;font-weight:600;';
                        filterSep.textContent = 'SDGSAT & VIIRS filters';
                        opacitySlidersDiv.appendChild(filterSep);

                        var sdgsatFilterRefs = [];  // [{slider, val, key, initial}]
                        function makeSdgsatFilterRow(label, filterKey, min, max, step, initial) {
                            var row = document.createElement('div');
                            row.style.cssText = 'display:flex;align-items:center;gap:8px;margin-bottom:2px;';
                            var lbl = document.createElement('span');
                            lbl.textContent = label;
                            lbl.style.minWidth = '70px';
                            var slider = document.createElement('input');
                            slider.type = 'range';
                            slider.min = String(min);
                            slider.max = String(max);
                            slider.step = String(step);
                            slider.value = String(initial);
                            slider.style.flex = '1';
                            var val = document.createElement('span');
                            val.className = 'mono';
                            val.textContent = parseFloat(initial).toFixed(2);
                            val.style.cssText = 'min-width:28px;text-align:right;';
                            slider.addEventListener('input', function() {
                                var v = parseFloat(this.value);
                                sdgsatFilters[filterKey] = v;
                                val.textContent = v.toFixed(2);
                                applySdgsatFilters();
                            });
                            L.DomEvent.disableClickPropagation(slider);
                            L.DomEvent.disableScrollPropagation(slider);
                            slider.addEventListener('mousedown', function(e) { e.stopPropagation(); });
                            slider.addEventListener('mouseup', function(e) { e.stopPropagation(); });
                            row.appendChild(lbl);
                            row.appendChild(slider);
                            row.appendChild(val);
                            sdgsatFilterRefs.push({ slider: slider, val: val, key: filterKey, initial: initial });
                            return row;
                        }

                        opacitySlidersDiv.appendChild(makeSdgsatFilterRow('Brightness', 'brightness', 0, 1, 0.05, 0.5));
                        opacitySlidersDiv.appendChild(makeSdgsatFilterRow('Contrast',   'contrast',   0, 1, 0.05, 0.5));
                        opacitySlidersDiv.appendChild(makeSdgsatFilterRow('Saturation', 'saturate',   0, 1, 0.05, 0.5));

                        // Reset button for the SDGSAT + VIIRS filters — lives in the
                        // header of the panel to save vertical space in the body.
                        var sdgsatResetBtn = document.createElement('button');
                        sdgsatResetBtn.type = 'button';
                        sdgsatResetBtn.className = 'ds-panel-reset';
                        sdgsatResetBtn.title = 'Reset SDGSAT & VIIRS filters';
                        sdgsatResetBtn.innerHTML =
                            '<svg class="ds-icon" viewBox="0 0 24 24" fill="none" ' +
                            'stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">' +
                            '<path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5"/></svg>Reset';
                        sdgsatResetBtn.addEventListener('click', function () {
                            sdgsatFilterRefs.forEach(function (r) {
                                r.slider.value = String(r.initial);
                                r.val.textContent = parseFloat(r.initial).toFixed(2);
                                sdgsatFilters[r.key] = r.initial;
                            });
                            applySdgsatFilters();
                        });
                        L.DomEvent.disableClickPropagation(sdgsatResetBtn);
                        header.appendChild(sdgsatResetBtn);

                        return outer;
                    },
                    onRemove: function() {}
                });
                L.control.opacitySliders = function(opts) { return new L.Control.OpacitySliders(opts); };
                L.control.opacitySliders({ position: 'bottomleft' }).addTo(map);

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
                    // Don't accept clicks while the tutorial is showing.
                    if (window.LAN && window.LAN.tutorialActive) return;
                    if (isTurn === 'image') {
                        var T = window.LAN_I18N || {};
                        showAlert(T.wrong_place_title || 'Wrong place!',
                                  T.wrong_place_image || 'Please add the control point on the image first.');
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
                      

                        // If we don't drag the image, add an icon (unless the
                        // tutorial overlay is active — clicks during the tour
                        // shouldn't create control points).
                        if (!isDragged && !(window.LAN && window.LAN.tutorialActive)) {
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
                                var T = window.LAN_I18N || {};
                                showAlert(T.wrong_place_title || 'Wrong place!',
                                          T.wrong_place_map || 'Please add a point in the map (related to the last control point).');
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
            var body = {};
            try { body = response.responseJSON || JSON.parse(response.responseText || '{}'); }
            catch (e) {}

            var T = window.LAN_I18N || {};

            // 409 with challenge_conflict: pool empty because of active
            // enrollments. Tell the user and link to the challenge detail
            // where they can leave it if they want different tasks.
            if (response.status === 409 && body.challenge_conflict) {
                var manyChallenges = (body.challenges || []).length !== 1;
                var noMatchTxt = manyChallenges
                    ? (T.no_match_many || 'There are no photos left that count for your challenges')
                    : (T.no_match_one  || 'There are no photos left that count for your challenge');
                var firstCh = (body.challenges || [])[0];
                var nameHtml = '';
                if (firstCh) {
                    nameHtml = ' (<a href="/challenges/' + firstCh.id + '/"><b>' + firstCh.name + '</b></a>)';
                }
                var actionsHtml = '<div style="display:flex;flex-wrap:wrap;gap:8px;">';
                if (firstCh) {
                    actionsHtml += '<a href="/challenges/' + firstCh.id + '/" class="ds-btn ds-btn--primary">'
                        + (T.btn_view_challenge || 'View challenge') + '</a>';
                }
                actionsHtml += '<a href="/#challenges-section" class="ds-btn ds-btn--secondary">'
                    + (T.btn_browse_challenges || 'Browse challenges') + '</a>'
                    + '<a href="/" class="ds-btn ds-btn--ghost">'
                    + (T.btn_go_home || 'Go home') + '</a>'
                    + '</div>';
                var html = ''
                    + '<p>'
                    + noMatchTxt
                    + nameHtml
                    + '.</p>'
                    + '<p style="margin:10px 0 14px;color:var(--ink-2);font-size:12.5px;">'
                    + (T.leave_to_change || 'You can leave the challenge from its page if you want different tasks.')
                    + '</p>'
                    + actionsHtml;
                showAlert(T.challenge_active || 'Your challenge has no tasks left', html);
                return;
            }

            // 404 = no pending tasks left in the batch (or globally).
            if (response.status === 404) {
                var emptyHtml = ''
                    + '<div style="text-align:center;padding:8px 4px 14px;">'
                    + '<div style="font-size:42px;margin-bottom:8px;">🎉</div>'
                    + '<p style="margin:0 0 8px;color:var(--ink-0);font-weight:600;">'
                    + (T.all_done_heading || 'No more tasks available here')
                    + '</p>'
                    + '<p style="margin:0 0 18px;color:var(--ink-2);font-size:13px;line-height:1.5;">'
                    + (T.all_done_body || 'Either every image in this batch has been georeferenced enough times, or there are no pending tasks at the moment. Thank you for contributing!')
                    + '</p>'
                    + '<div style="display:inline-flex;flex-wrap:wrap;gap:8px;justify-content:center;">'
                    + '<a href="/#challenges-section" class="ds-btn ds-btn--primary">'
                    + (T.btn_browse_challenges || 'Browse challenges') + '</a>'
                    + '<a href="/" class="ds-btn ds-btn--ghost">'
                    + (T.btn_go_home || 'Go home') + '</a>'
                    + '</div>'
                    + '</div>';
                showAlert(T.all_done_title || 'All done here', emptyHtml);
                return;
            }

            // Network error (no response) or 5xx.
            var msg = body.error || (T.error_generic || 'An error occurred.');
            showAlert(T.error_title || 'Error',
                msg + '<br /><br /><a href="/" class="ds-btn ds-btn--primary ds-btn--sm">'
                + (T.btn_go_home || 'Go home') + '</a>');
        }

    });
});
