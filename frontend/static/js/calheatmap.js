document.addEventListener('DOMContentLoaded', function() {
    // Fechas básicas
    const startDate = new Date();
    startDate.setFullYear(startDate.getFullYear() - 1);
    const currentDate = new Date();
    const endDate = new Date(currentDate.getFullYear(), currentDate.getMonth() + 1, 0);
    
    console.log("Date range:", startDate, "to", endDate);
    
    // Actualizar título si existe
    const contributionsTitle = document.getElementById('contributions-title');
    if (contributionsTitle) {
        const formattedStartDate = startDate.toLocaleDateString('es-ES', { month: 'long', year: 'numeric' });
        const formattedEndDate = endDate.toLocaleDateString('es-ES', { month: 'long', year: 'numeric' });
        contributionsTitle.textContent = `Contribuciones desde ${formattedStartDate} hasta ${formattedEndDate}`;
    }

    // Obtener datos
    fetch('/api/v1/geoattempts-calendar/')
    .then(response => response.json())
    .then(data => {
        console.log("API returned data:", data);
        
        // Mostrar datos no-cero para depuración
        const nonZeroEntries = data.filter(item => item.count > 0);
        console.log("Non-zero entries:", nonZeroEntries);
        
        // Crear el calendario
        const cal = new CalHeatmap();
        
        try {
            cal.paint({
                data: {
                    source: data, 
                    x: 'date',
                    y: 'count'
                },
                itemSelector: '#github-like-heatmap',
                domain: { type: 'month' },
                subDomain: { type: 'day', radius: 2 },
                date: { start: startDate },
                range: 13,
                scale: { 
                    color: { 
                        type: 'threshold',
                        range: ['#ffffff', '#fff', '#40c463', '#30a14e', '#216e39'],
                        domain: [0, 1, 4, 6, 8]
                    }
                }
            });
        } catch (e) {
            console.error("Error rendering calendar:", e);
            const heatmapContainer = document.getElementById('github-like-heatmap');
            if (heatmapContainer) {
                heatmapContainer.innerHTML = '<div class="alert alert-danger">Error rendering calendar.</div>';
            }
        }
    })
    .catch(error => {
        console.error('Error loading calendar data:', error);
        const heatmapContainer = document.getElementById('github-like-heatmap');
        if (heatmapContainer) {
            heatmapContainer.innerHTML = '<div class="alert alert-danger">Error loading calendar data.</div>';
        }
    });
});