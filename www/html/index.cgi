#!/bin/sh

MEDIA_DIR="/var/www/html/media"

# --- 1. API Logic (Backend) ---
QUERY_STRING="$QUERY_STRING"

if echo "$QUERY_STRING" | grep -q "action="; then
    
    ACTION=$(echo "$QUERY_STRING" | grep -o 'action=[a-z]*' | cut -d= -f2)
    CAM=$(echo "$QUERY_STRING" | grep -o 'cam=[0-9]*' | cut -d= -f2)
    VAL=$(echo "$QUERY_STRING" | grep -o 'val=[a-z]*' | cut -d= -f2)
    
    # List Files
    if [ "$ACTION" = "listfiles" ]; then
        echo "Content-type: application/json"
        echo ""
        echo "["
        if [ -d "$MEDIA_DIR" ]; then
            cd "$MEDIA_DIR"
            find . -type f \( -name "*.jpg" -o -name "*.mkv" \) | sed 's|^\./||' | awk '{printf "\"%s\",", $0}' | sed 's/,$//'
        fi
        echo "]"
        exit 0
    fi

    # Motion Commands
    echo "Content-type: text/plain"
    echo ""
    
    MOTION_URL="http://localhost:8080/$CAM"

    if [ "$ACTION" = "snapshot" ]; then
        curl -s "$MOTION_URL/action/snapshot"
        echo "Snapshot OK"

    elif [ "$ACTION" = "recordstart" ]; then
        # Ensures the threshold is lowered to accept the manual event.
        curl -s "$MOTION_URL/config/set?threshold=1500"
        curl -s "$MOTION_URL/action/eventstart"
        echo "Recording Force Started"

    elif [ "$ACTION" = "recordstop" ]; then
        curl -s "$MOTION_URL/action/eventend"
        echo "Recording Stopped"

    elif [ "$ACTION" = "detection" ]; then
        if [ "$VAL" = "on" ]; then
            curl -s "$MOTION_URL/config/set?threshold=1500"
            curl -s "$MOTION_URL/detection/start"
            echo "Detection ACTIVE (Auto)"
        else
            curl -s "$MOTION_URL/detection/pause"
            echo "Detection PAUSED (Manual Only)"
        fi
    fi
    exit 0
fi

# --- 2. Graphical Interface (Frontend) ---
echo "Content-type: text/html"
echo ""

cat << EOF
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ARCOP Security Dashboard</title>
    <style>
        body { margin: 0; font-family: 'Segoe UI', sans-serif; background: #1a1a1a; color: white; display: flex; flex-direction: column; height: 100vh; }
        #main-container { display: flex; flex-grow: 1; overflow: hidden; }
        #video-area { flex-grow: 1; background: #000; position: relative; display: flex; align-items: center; justify-content: center; }
        .single-view { max-width: 100%; max-height: 100%; object-fit: contain; }
        .grid-view { display: grid; width: 100%; height: 100%; grid-template-columns: repeat(auto-fit, minmax(45%, 1fr)); gap: 4px; padding: 4px; box-sizing: border-box; }
        .grid-item { position: relative; background: #222; border: 1px solid #444; display: flex; align-items: center; justify-content: center; overflow: hidden; }
        .grid-item img { width: 100%; height: 100%; object-fit: contain; }
        .cam-overlay { position: absolute; top: 10px; left: 10px; background: rgba(0,0,0,0.6); padding: 4px 8px; border-radius: 4px; color: #00aaff; font-weight: bold; }
        
        #files-panel { width: 300px; background: #222; border-left: 1px solid #444; display: flex; flex-direction: column; transition: width 0.3s; }
        #files-header { padding: 15px; border-bottom: 1px solid #333; display: flex; justify-content: space-between; align-items: center; }
        #file-tree { overflow-y: auto; flex-grow: 1; padding: 10px; }
        
        details { margin-left: 10px; margin-bottom: 5px; }
        summary { cursor: pointer; list-style: none; font-weight: bold; padding: 5px; color: #ddd; }
        summary:hover { color: #fff; background: #333; border-radius: 4px; }
        summary::before { content: '▶ '; font-size: 0.8em; color: #00aaff; display: inline-block; width: 15px; transition: transform 0.2s; }
        details[open] > summary::before { transform: rotate(90deg); }
        
        .file-item { display: block; margin-left: 25px; padding: 4px 8px; color: #aaa; text-decoration: none; font-size: 0.9em; border-left: 1px solid #444; }
        .file-item:hover { color: #00aaff; background: #2a2a2a; }
        .file-icon { margin-right: 5px; }
        
        #controls { background: #333; padding: 15px; display: flex; gap: 15px; align-items: center; justify-content: center; border-top: 2px solid #00aaff; }
        button { padding: 10px 15px; border: none; border-radius: 4px; cursor: pointer; font-weight: bold; transition: 0.2s; white-space: nowrap; display: flex; align-items: center; gap: 8px;}
        .btn-cam { background: #444; color: white; }
        .btn-cam.active { background: #00aaff; color: black; }
        .btn-snap { background: #f1c40f; color: black; }
        .btn-record { background: #e74c3c; color: white; min-width: 130px; justify-content: center; }
        .btn-record.recording { background: #c0392b; animation: pulse 2s infinite; border: 1px solid #ff9999; }
        @keyframes pulse { 0% { box-shadow: 0 0 0 0 rgba(231, 76, 60, 0.7); } 70% { box-shadow: 0 0 0 10px rgba(231, 76, 60, 0); } 100% { box-shadow: 0 0 0 0 rgba(231, 76, 60, 0); } }
        
        /* Detection Button */
        .btn-detect { background: #555; color: #aaa; border: 1px solid #666; min-width: 110px; justify-content: center; }
        .btn-detect.active { background: #2ecc71; color: white; border: 1px solid #27ae60; }
        
        .hidden { display: none !important; }
        .timer { font-family: monospace; font-size: 1.1em; background: rgba(0,0,0,0.3); padding: 2px 5px; border-radius: 3px; }
    </style>
</head>
<body>
    <div id="main-container">
        <div id="video-area"></div>
        <div id="files-panel" class="hidden">
            <div id="files-header">
                <span>📂 Files</span>
                <button style="padding:2px 8px; font-size:0.8em; background:#444; color:white;" onclick="loadFiles()">↻</button>
            </div>
            <div id="file-tree"><p style="color:#666; text-align:center; margin-top:20px;">Loading...</p></div>
        </div>
    </div>
    
    <div id="controls">
        <div id="cam-buttons" style="display:flex; gap:10px;"></div>
        <div style="width: 2px; height: 30px; background: #555; margin: 0 5px;"></div>
        
        <button id="btn-detect" class="btn-detect" onclick="toggleDetection()">
            <span id="detect-icon">🛡️</span> <span id="detect-text">MANUAL</span>
        </button>

        <div style="width: 2px; height: 30px; background: #555; margin: 0 5px;"></div>

        <button id="btn-snap" class="btn-snap" onclick="takeSnapshot()">📸 SNAP</button>
        <button id="btn-record" class="btn-record" onclick="toggleRecord()">
            <div id="rec-icon">●</div><span id="rec-text">REC</span><span id="rec-timer" class="timer hidden">00:00</span>
        </button>
        
        <div style="width: 2px; height: 30px; background: #555; margin: 0 5px;"></div>
        <button class="btn-cam" onclick="toggleFilePanel()" id="btn-files">📂</button>
    </div>

    <script>
        const cameras = { 1: { port: 8081, label: "CAM 1" }, 2: { port: 8082, label: "CAM 2" } };
        let currentMode = '1'; 
        const host = window.location.hostname;
        
        // --- State Management ---
        let recordState = JSON.parse(localStorage.getItem('recordState')) || {};
        let detectState = JSON.parse(localStorage.getItem('detectState')) || {};

        for(let id in cameras) { 
            if(!recordState[id]) recordState[id] = { isRecording: false, startTime: null }; 
            if(detectState[id] === undefined) detectState[id] = false; 
        }

        function init() {
            renderCamButtons();
            selectCam(1);
            setInterval(updateRecordUI, 1000);
            
            // Carregar ficheiros no arranque (garante que funciona)
            loadFiles(); 
            
            // Força estado da deteção (Manual/Auto) no arranque
            for(let id in cameras) { enforceDetectionState(id); }
        }

        function renderCamButtons() {
            const container = document.getElementById('cam-buttons');
            let html = '';
            for (const [id, info] of Object.entries(cameras)) {
                html += \`<button id="btn-cam-\${id}" class="btn-cam" onclick="selectCam(\${id})">\${info.label}</button>\`;
            }
            html += \`<button id="btn-cam-all" class="btn-cam" onclick="selectAll()">👁️ ALL</button>\`;
            container.innerHTML = html;
        }

        function selectCam(id) {
            currentMode = id;
            document.querySelectorAll('.btn-cam').forEach(b => b.classList.remove('active'));
            document.getElementById('btn-cam-' + id).classList.add('active');
            
            const port = cameras[id].port;
            document.getElementById('video-area').innerHTML = \`
                <img class="single-view" src="http://\${host}:\${port}/" onerror="this.alt='No Signal'">
                <div class="cam-overlay">\${cameras[id].label}</div>
            \`;
            
            updateRecordUI();
            updateDetectUI();
            
            document.getElementById('btn-snap').disabled = false;
            document.getElementById('btn-record').disabled = false;
            document.getElementById('btn-detect').disabled = false;
        }

        function selectAll() {
            currentMode = 'all';
            document.querySelectorAll('.btn-cam').forEach(b => b.classList.remove('active'));
            document.getElementById('btn-cam-all').classList.add('active');
            
            let gridHtml = '<div class="grid-view">';
            for (const [id, info] of Object.entries(cameras)) {
                gridHtml += \`
                    <div class="grid-item">
                        <img src="http://\${host}:\${info.port}/" onerror="this.alt='Offline'">
                        <div class="cam-overlay">\${info.label}</div>
                    </div>
                \`;
            }
            gridHtml += '</div>';
            document.getElementById('video-area').innerHTML = gridHtml;
            
            document.getElementById('btn-snap').disabled = true;
            document.getElementById('btn-record').disabled = true;
            document.getElementById('btn-detect').disabled = true;
            document.getElementById('rec-text').innerText = "SELECT CAM";
            document.getElementById('rec-timer').classList.add('hidden');
        }

        // --- FILES LOGIC ---
        function toggleFilePanel() {
            const p = document.getElementById('files-panel');
            p.classList.toggle('hidden');
            if (!p.classList.contains('hidden')) loadFiles();
        }

        async function loadFiles() {
            const treeContainer = document.getElementById('file-tree');
            treeContainer.innerHTML = '<p style="text-align:center">Updating...</p>';
            try {
                // Timestamp evita cache
                const response = await fetch('index.cgi?action=listfiles&_t=' + new Date().getTime());
                const files = await response.json();
                
                if (files.length === 0) {
                    treeContainer.innerHTML = '<p style="text-align:center; color:#666">No files found.</p>';
                    return;
                }
                const tree = {};
                files.forEach(path => {
                    const parts = path.split('/'); 
                    if (parts.length < 2) return;
                    const camFolder = parts[0]; 
                    const filename = parts[1];  
                    if (!tree[camFolder]) tree[camFolder] = { 'Snapshots': [], 'Recordings': [] };
                    if (filename.endsWith('.jpg')) tree[camFolder]['Snapshots'].push(path);
                    else if (filename.endsWith('.mkv') || filename.endsWith('.avi')) tree[camFolder]['Recordings'].push(path);
                });
                let html = '';
                Object.keys(tree).sort().forEach(cam => {
                    const camLabel = cam.replace('cam', 'Cam ').toUpperCase();
                    html += \`<details open><summary>\${camLabel}</summary>\`;
                    ['Snapshots', 'Recordings'].forEach(type => {
                        const items = tree[cam][type];
                        if (items.length > 0) {
                            html += \`<details style="margin-left:15px"><summary style="font-size:0.9em; color:#bbb">\${type} (\${items.length})</summary>\`;
                            items.sort().reverse(); 
                            items.forEach(filePath => {
                                const fileName = filePath.split('/').pop();
                                const icon = type === 'Snapshots' ? '🖼️' : '🎬';
                                html += \`<a href="/media/\${filePath}" target="_blank" class="file-item">
                                    <span class="file-icon">\${icon}</span> \${fileName}
                                </a>\`;
                            });
                            html += \`</details>\`;
                        }
                    });
                    html += \`</details>\`;
                });
                treeContainer.innerHTML = html;
            } catch (e) {
                treeContainer.innerHTML = '<p style="color:red">Error loading files.</p>';
                console.error(e);
            }
        }

        // --- DETECTION ---
        function toggleDetection() {
            if (currentMode === 'all') return;
            const isCurrentlyAuto = detectState[currentMode];
            const newState = !isCurrentlyAuto; 
            
            detectState[currentMode] = newState;
            localStorage.setItem('detectState', JSON.stringify(detectState));
            updateDetectUI();
            enforceDetectionState(currentMode);
        }

        function enforceDetectionState(camId) {
            const isAuto = detectState[camId];
            const val = isAuto ? 'on' : 'off';
            const url = "index.cgi?action=detection&val=" + val + "&cam=" + camId + "&_t=" + new Date().getTime();
            fetch(url).catch(e => console.error("Sync Error:", e));
        }

        function updateDetectUI() {
            if (currentMode === 'all') return;
            const btn = document.getElementById('btn-detect');
            const icon = document.getElementById('detect-icon');
            const text = document.getElementById('detect-text');
            const isAuto = detectState[currentMode];

            if (isAuto) {
                btn.classList.add('active');
                icon.innerText = "👀"; 
                text.innerText = "AUTO";
            } else {
                btn.classList.remove('active');
                icon.innerText = "🛡️"; 
                text.innerText = "MANUAL";
            }
        }

        // --- RECORDING ---
        function toggleRecord() {
            if (currentMode === 'all') return;
            const state = recordState[currentMode];
            const action = state.isRecording ? 'recordstop' : 'recordstart';
            const url = "index.cgi?action=" + action + "&cam=" + currentMode + "&_t=" + new Date().getTime();

            fetch(url)
                .then(r => r.text())
                .then(resp => {
                    console.log("Record Resp:", resp);
                    if (!state.isRecording) {
                        state.isRecording = true;
                        state.startTime = Date.now();
                    } else {
                        state.isRecording = false;
                        state.startTime = null;
                        setTimeout(loadFiles, 2000); 
                    }
                    saveState();
                    updateRecordUI();
                })
                .catch(e => alert("Error: " + e));
        }
        
        function updateRecordUI() {
            if (currentMode === 'all') return;
            const btn = document.getElementById('btn-record');
            const icon = document.getElementById('rec-icon');
            const text = document.getElementById('rec-text');
            const timer = document.getElementById('rec-timer');
            const state = recordState[currentMode];
            
            if (state && state.isRecording) {
                btn.classList.add('recording');
                icon.innerText = "⏹";
                text.innerText = "STOP";
                timer.classList.remove('hidden');
                
                const diff = Math.floor((Date.now() - state.startTime) / 1000);
                const mm = String(Math.floor(diff / 60)).padStart(2, '0');
                const ss = String(diff % 60).padStart(2, '0');
                timer.innerText = \`\${mm}:\${ss}\`;
            } else {
                btn.classList.remove('recording');
                icon.innerText = "●";
                text.innerText = "REC";
                timer.classList.add('hidden');
            }
        }

        function saveState() { localStorage.setItem('recordState', JSON.stringify(recordState)); }
        
        function takeSnapshot() {
            const url = "index.cgi?action=snapshot&cam=" + currentMode + "&_t=" + new Date().getTime();
            fetch(url).then(() => { setTimeout(loadFiles, 1000); });
        }

        init();
    </script>
</body>
</html>
EOF
