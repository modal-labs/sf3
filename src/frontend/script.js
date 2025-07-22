class StreetFighterGame {

    constructor() {
        this.socket = null;

        // game state

        this.gameLoaded = false;
        this.serverReady = false;

        this.firstFrameReceived = false;
        this.renderLoopStarted = false;
        this.frameQueue = [];
        this.lastFrameTime = 0;
        this.targetFPS = 60;
        this.frameInterval = 1000 / this.targetFPS;

        this.keyState = {};
        this.inputHistory = [];
        this.maxInputHistory = 20;
        this.movesByLength = {};
        this.allCombos = {};
        this.allSpecialMoves = {};

        this.currentCharacter = 'Ken';
        this.playerDirection = 'right';  // since for display, not necessary to show left

        this.gameSettings = {
            difficulty: 1,
            player1: {
                character: 'Ken',
                outfit: 1,
                superArt: 1
            },
            player2: {
                character: 'Ken',
                outfit: 1,
                superArt: 1
            }
        };
        this.actions = {

            // basic actions

            NONE: 0,

            // directional

            LEFT: 1,
            LEFT_UP: 2,
            UP: 3,
            RIGHT_UP: 4,
            RIGHT: 5,
            RIGHT_DOWN: 6,
            DOWN: 7,
            LEFT_DOWN: 8,

            // attacks

            LIGHT_PUNCH: 9,
            MEDIUM_PUNCH: 10,
            HEAVY_PUNCH: 11,
            LIGHT_KICK: 12,
            MEDIUM_KICK: 13,
            HEAVY_KICK: 14,

            // combinations
            
            LP_LK: 15,
            MP_MK: 16,
            HP_HK: 17,

            // super arts
            SUPER_ART: 18,
            
            // combos
            COMBO: 19,
        };
    
        // event listeners

        const handleKeyEvent = (e, isDown) => {
            if (!this.gameLoaded) return;

            this.keyState[e.code] = isDown;
            const action = this.getActionFromKeys();
            this.sendAction(action, this.maxInputHistory);
            e.preventDefault();
        };

        document.addEventListener('keydown', (e) => handleKeyEvent(e, true));
        document.addEventListener('keyup', (e) => handleKeyEvent(e, false));

        // ui

        this.setScreen('block', 'none', 'none', 'none', 'none');

        const loadExtraMovesDisplay = async () => {
            const combosLoading = document.getElementById('combos-loading');
            const superArtsLoading = document.getElementById('super-arts-loading');
            const combosList = document.getElementById('combos-list');
            const superArtsList = document.getElementById('super-arts-list');

            try {
                const response = await fetch('/api/extra-moves');
                const data = await response.json();
                this.allCombos = data.combos;
                this.allSpecialMoves = data.special_moves;
                
                this.preprocessMoves();
                
                const characterSelect = document.getElementById('character-select');
                this.currentCharacter = characterSelect.value;
                
                const superArtSelect = document.getElementById('super-art-select');
                this.gameSettings.player1.superArt = parseInt(superArtSelect.value);
                
                characterSelect.addEventListener('change', () => {
                    this.currentCharacter = characterSelect.value;
                    this.updateCombosDisplay(characterSelect.value);
                    this.updateSuperArtsDisplay(characterSelect.value);
                    this.preprocessMoves();
                });
                
                superArtSelect.addEventListener('change', () => {
                    this.gameSettings.player1.superArt = parseInt(superArtSelect.value);
                    this.updateSuperArtsDisplay(characterSelect.value);
                    this.preprocessMoves();
                });
                
                combosLoading.classList.add('hidden');
                superArtsLoading.classList.add('hidden');
                
                this.updateCombosDisplay(characterSelect.value);
                this.updateSuperArtsDisplay(characterSelect.value);
            } catch (error) {
                console.error('Failed to load combos:', error);
                
                combosLoading.classList.add('hidden');
                superArtsLoading.classList.add('hidden');
                combosList.innerHTML = '<p class="text-red-500">Failed to load combos</p>';
                superArtsList.innerHTML = '<p class="text-red-500">Failed to load super arts</p>';
            }
        };
        
        loadExtraMovesDisplay();

        const slider = document.getElementById('difficulty-slider');
        const label = document.getElementById('difficulty-label');
        const difficultyLabels = {
            1: 'Very Easy',
            2: 'Easy',
            3: 'Medium',
            4: 'Hard',
            5: 'Very Hard',
            6: 'Expert',
            7: 'Master',
            8: 'Extreme'
        };
        slider.addEventListener('input', (e) => {
            const value = parseInt(e.target.value);
            this.gameSettings.difficulty = value;
            label.textContent = difficultyLabels[value];
        });

        // backend websocket

        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;
        
        this.socket = new WebSocket(wsUrl);
        
        this.socket.onopen = () => {
            console.log('Connected to server');
        };
        
        this.socket.onclose = () => {
            console.log('Disconnected from server');
            if (!this.serverReady) {
                startButton.textContent = 'Connection Lost';
                startButton.disabled = true;
                startButton.classList.add('opacity-50');
            }
        };
        
        this.socket.onerror = (event) => {
            let msg = 'WebSocket connection error';
            console.error(msg, event);
            this.showError(msg);
            if (!this.serverReady) {
                startButton.textContent = 'Connection Error';
                startButton.disabled = true;
                startButton.classList.add('opacity-50');
            }
        };
        
        this.socket.onmessage = (event) => {
            const message = JSON.parse(event.data);
            
            switch (message.type) {
                case 'game_state':
                    console.log('Game state:', message.data.status);
    
                    if (!this.serverReady) {
                        this.serverReady = true;
                        startButton.disabled = false;
                        startButton.textContent = 'START GAME';
                        startButton.classList.remove('opacity-50');
                        console.log('Server ready');
                    }
    
                    switch (message.data.status) {
                        case 'initializing':
                            document.getElementById('loading-status').textContent = 'Starting game...';
                            break;
                        case 'running':
                            this.gameLoaded = true;
                            this.setScreen('none', 'none', 'block', 'none', 'none');
                            break;
                        case 'finished':
                            this.gameLoaded = false;
                            document.getElementById('winner-text').textContent = `Winner: ${message.data.winner || 'Unknown'}`;
                            this.setScreen('none', 'none', 'none', 'block', 'none');
                            break;
                        case 'error':
                            this.showError(message.data.error || 'Unknown game error');
                            break;
                    }
                    break;
                case 'game_frame':
                    this.frameQueue.push(message.data.frame);
                    
                    if (this.frameQueue.length > 3) {
                        this.frameQueue.shift();
                    }
                    
                    if (!this.firstFrameReceived) {
                        this.firstFrameReceived = true;
                        document.getElementById('canvas-loading-overlay').classList.add('hidden');
                    }
                    
                    if (!this.renderLoopStarted) {
                        this.renderLoopStarted = true;
                        this.startRenderLoop();
                    }
                    break;
            }
        };

        // main game logic

        const startGame = () => {
            
            // send settings to server

            this.gameSettings.player1.character = document.getElementById('character-select').value;
            this.gameSettings.player1.outfit = parseInt(document.getElementById('outfit-select').value);
            this.gameSettings.player1.superArt = parseInt(document.getElementById('super-art-select').value);
            this.gameSettings.player2.character = document.getElementById('character-select-p2').value;
            this.gameSettings.player2.outfit = parseInt(document.getElementById('outfit-select-p2').value);
            this.gameSettings.player2.superArt = parseInt(document.getElementById('super-art-select-p2').value);
            this.gameSettings.difficulty = parseInt(document.getElementById('difficulty-slider').value);

            // reset

            this.gameLoaded = false;
            this.serverReady = false;

            this.firstFrameReceived = false;
            this.renderLoopStarted = false;
            this.frameQueue = [];
            this.lastFrameTime = 0;

            this.keyState = {};
            this.inputHistory = [];

            const canvas = document.getElementById('game-canvas');
            const ctx = canvas.getContext('2d');
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            this.setScreen('none', 'block', 'none', 'none', 'none');

            document.getElementById('loading-status').textContent = 'Starting game...';
            
            // send start game message

            this.sendMessage('start_game', this.gameSettings);
        };

        // logic buttons

        const startButton = document.getElementById('start-game-btn');
        startButton.addEventListener('click', startGame);
        startButton.disabled = true;
        startButton.classList.add('opacity-50');

        const playAgainButton = document.getElementById('play-again-btn');
        playAgainButton.addEventListener('click', () => {
            this.setScreen('block', 'none', 'none', 'none', 'none');
        });
        
        const errorBackButton = document.getElementById('error-back-btn');   
        errorBackButton.addEventListener('click', () => {
            this.setScreen('block', 'none', 'none', 'none', 'none');
        });
    }

    // ui

    setScreen(settings, loading, game, win, error) {
        const screens = [
            { id: 'settings-screen', show: settings },
            { id: 'loading-screen', show: loading },
            { id: 'game-display', show: game },
            { id: 'win-screen', show: win },
            { id: 'error-screen', show: error }
        ];
        screens.forEach(screen => {
            const el = document.getElementById(screen.id);
            if (el) {
                if (screen.show !== 'none') {
                    el.classList.remove('hidden');
                } else {
                    el.classList.add('hidden');
                }
            }
        });
        
        const header = document.getElementById('game-header');
        if (header) {
            if (game !== 'none') {
                header.classList.add('hidden');
            } else {
                header.classList.remove('hidden');
            }
        }
    };

    showError(message) {
        document.getElementById('error-message').textContent = message;
        document.getElementById('error-details').textContent = new Date().toLocaleString() + '\n' + message;
        this.setScreen('none', 'none', 'none', 'none', 'block');
    }

    // backend websocket

    sendMessage(type, data) {
        if (this.socket && this.socket.readyState === WebSocket.OPEN) {
            this.socket.send(JSON.stringify({
                type: type,
                data: data
            }));
        }
    }

    // render loop

    startRenderLoop() {
        const renderFrame = (currentTime) => {
            requestAnimationFrame(renderFrame);
            
            if (!this.gameLoaded) return;
            
            const elapsed = currentTime - this.lastFrameTime;
            if (elapsed < this.frameInterval) return;
            
            this.lastFrameTime = currentTime - (elapsed % this.frameInterval);
            
            if (this.frameQueue.length > 0) {
                const frameData = this.frameQueue.shift();
                const canvas = document.getElementById('game-canvas');
                const ctx = canvas.getContext('2d');
                
                const img = new Image();
                img.onload = () => {
                    ctx.clearRect(0, 0, canvas.width, canvas.height);
                    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
                };
                img.src = 'data:image/jpeg;base64,' + frameData;
            }
        };
        
        requestAnimationFrame(renderFrame);
    }

    // extra moves

    preprocessMoves() {
        this.movesByLength = {};
        
        if (!this.currentCharacter) return;
        
        // super arts

        const characterMoves = this.allSpecialMoves[this.currentCharacter];
        if (characterMoves) {
            const selectedSuperArt = this.gameSettings.player1.superArt;
            
            for (const [moveKey, moveData] of Object.entries(characterMoves)) {
                if (moveKey.startsWith(`${selectedSuperArt} `)) {
                    const seq = moveData[this.playerDirection];
                    if (!this.movesByLength[seq.length]) this.movesByLength[seq.length] = [];
                    this.movesByLength[seq.length].push({
                        type: 'super_art',
                        name: moveKey,
                        sequence: seq
                    });
                    break;
                }
            }
            
            for (const [moveKey, moveData] of Object.entries(characterMoves)) {
                if (typeof moveKey === 'string' && moveKey.startsWith("Max")) {
                    if (moveKey.startsWith(`Max-${selectedSuperArt} `) || 
                        moveKey.startsWith("Max ")) {
                        const seq = moveData[this.playerDirection];
                        if (!this.movesByLength[seq.length]) this.movesByLength[seq.length] = [];
                        this.movesByLength[seq.length].push({
                            type: 'super_art',
                            name: moveKey,
                            sequence: seq
                        });
                    }
                }
            }
        }
        
        // combos

        const characterCombos = this.allCombos[this.currentCharacter];
        if (characterCombos) {
            for (const [comboName, comboData] of Object.entries(characterCombos)) {
                const seq = comboData[this.playerDirection];
                if (!this.movesByLength[seq.length]) this.movesByLength[seq.length] = [];
                this.movesByLength[seq.length].push({
                    type: 'combo',
                    name: comboName,
                    sequence: seq
                });
            }
        }
        
        for (const length in this.movesByLength) {
            this.movesByLength[length].sort((a, b) => {
                if (a.type === 'super_art' && b.type === 'combo') return -1;
                if (a.type === 'combo' && b.type === 'super_art') return 1;
                return 0;
            });
        }
    }

    getActionFromKeys() {
        const hasLP = this.keyState['KeyJ'];
        const hasMP = this.keyState['KeyK'];
        const hasHP = this.keyState['KeyL'];
        const hasLK = this.keyState['KeyU'];
        const hasMK = this.keyState['KeyI'];
        const hasHK = this.keyState['KeyO'];

        if (hasLP && hasLK) return this.actions.LP_LK;
        if (hasMP && hasMK) return this.actions.MP_MK;
        if (hasHP && hasHK) return this.actions.HP_HK;

        if (hasHP) return this.actions.HEAVY_PUNCH;
        if (hasMP) return this.actions.MEDIUM_PUNCH;
        if (hasLP) return this.actions.LIGHT_PUNCH;
        if (hasHK) return this.actions.HEAVY_KICK;
        if (hasMK) return this.actions.MEDIUM_KICK;
        if (hasLK) return this.actions.LIGHT_KICK;

        const left = this.keyState['KeyA'] || this.keyState['ArrowLeft'];
        const right = this.keyState['KeyD'] || this.keyState['ArrowRight'];
        const up = this.keyState['KeyW'] || this.keyState['ArrowUp'];
        const down = this.keyState['KeyS'] || this.keyState['ArrowDown'];

        if (left && up) return this.actions.LEFT_UP;
        if (right && up) return this.actions.RIGHT_UP;
        if (left && down) return this.actions.LEFT_DOWN;
        if (right && down) return this.actions.RIGHT_DOWN;

        if (left) return this.actions.LEFT;
        if (right) return this.actions.RIGHT;
        if (up) return this.actions.UP;
        if (down) return this.actions.DOWN;

        return this.actions.NONE;
    }

    detectExtra() {

        // shift out old inputs

        const comboTimeout = 200; // ms

        const currentTime = Date.now();

        while (this.inputHistory.length > 0 && 
               currentTime - this.inputHistory[0].time > comboTimeout) {
            this.inputHistory.shift();
        }
        
        // check for extra moves

        if (this.inputHistory.length < 2) return null;
        
        const inputLength = this.inputHistory.length;
        
        for (let len = inputLength; len >= 2; len--) {
            const moves = this.movesByLength[len];
            if (!moves) continue;
            
            const startIndex = inputLength - len;
            
            for (const move of moves) {
                let match = true;
                
                for (let i = 0; i < len; i++) {
                    if (this.inputHistory[startIndex + i].action !== move.sequence[i]) {
                        match = false;
                        break;
                    }
                }
                
                if (match) {
                    this.inputHistory = [];
                    return { type: move.type, name: move.name };
                }
            }
        }
        
        return null;
    }

    sendAction(action) {
        if (action !== this.actions.NONE) {
            this.inputHistory.push({
                action: action,
                time: Date.now()
            });
            
            if (this.inputHistory.length > this.maxInputHistory) {
                this.inputHistory.shift();
            }
        }
        
        const detectedMove = this.detectExtra();
        if (detectedMove) {
            if (detectedMove.type === 'super_art') {
                this.sendMessage('player_action', { 
                    action: 18,
                    super_art: detectedMove.name
                });
            } else if (detectedMove.type === 'combo') {
                this.sendMessage('player_action', { 
                    action: 19,
                    combo: detectedMove.name 
                });
            }
        } else {
            this.sendMessage('player_action', { action: action });
        }
    }

    updateCombosDisplay(character) {
        const combosList = document.getElementById('combos-list');

        const combos = this.allCombos[character];
        
        let html = '<div class="space-y-8">';
        for (const [comboName, comboData] of Object.entries(combos)) {
            const sequence = comboData[this.playerDirection];
            const displayElements = this.getExtraElements(sequence);
            
            html += `
                <div class="flex flex-col md:flex-row items-center md:items-center gap-2 md:gap-4">
                    <strong class="text-gray-300 text-center md:text-left md:w-60 md:flex-shrink-0">${comboName}:</strong>
                    <div class="flex items-center gap-x-1 gap-y-4 flex-wrap justify-center md:justify-start">
                        ${displayElements}
                    </div>
                </div>
            `;
        }
        html += '</div>';
        
        combosList.innerHTML = html;
    }
    
    updateSuperArtsDisplay(character) {
        const superArtsList = document.getElementById('super-arts-list');

        const selectedSuperArt = document.getElementById('super-art-select').value;
        const characterMoves = this.allSpecialMoves[character];
        const available = {};
        
        for (const [moveKey, moveData] of Object.entries(characterMoves)) {
            if (moveKey.startsWith(`${selectedSuperArt} `)) {
                available[moveKey] = moveData;
                break;
            }
        }
        
        for (const [moveKey, moveData] of Object.entries(characterMoves)) {
            if (typeof moveKey === 'string' && moveKey.startsWith("Max")) {
                if (moveKey.startsWith(`Max-${selectedSuperArt} `) || 
                    moveKey.startsWith("Max ")) {
                    available[moveKey] = moveData;
                }
            }
        }
        
        let html = '<div class="space-y-8">';
        for (const [superArtKey, superArtData] of Object.entries(available)) {
            const sequence = superArtData[this.playerDirection];
            const displayElements = this.getExtraElements(sequence);
            const displayName = this.getSpecialMoveDisplayName(superArtKey);
            
            html += `
                <div class="flex flex-col md:flex-row items-center md:items-center gap-2 md:gap-4">
                    <strong class="text-gray-300 text-center md:text-left md:w-60 md:flex-shrink-0">${displayName}:</strong>
                    <div class="flex items-center gap-x-1 gap-y-4 flex-wrap justify-center md:justify-start">
                        ${displayElements}
                    </div>
                </div>
            `;
        }
        html += '</div>';
        
        superArtsList.innerHTML = html;
    }

    getExtraElements(sequence) {        
        const actionNames = {
            1: '←', 2: '↖', 3: '↑', 4: '↗', 
            5: '→', 6: '↘', 7: '↓', 8: '↙',
            9: 'J', 10: 'K', 11: 'L',
            12: 'U', 13: 'I', 14: 'O',
            15: 'J + U', 16: 'K + I', 17: 'L + O'
        };
        
        return sequence.map((action, index) => {
            const symbol = actionNames[action] || '?';
            const isLast = index === sequence.length - 1;
            return `
                <span class="text-gray-300 font-mono bg-sf-dark-2 px-3 py-1 rounded border border-sf-green/50">${symbol}</span>
                ${!isLast ? '<span class="text-gray-500">+</span>' : ''}
            `;
        }).join('');
    }
    
    getSpecialMoveDisplayName(fullKey) {
        if (fullKey.match(/^\d+ /)) {
            // Format: "1 Messatsu Gou Hadou" -> "Messatsu Gou Hadou"
            return fullKey.substring(2);
        } else if (fullKey.startsWith("Max-")) {
            // Format: "Max-1 Messatsu Gou Hadou" -> "Max Messatsu Gou Hadou"
            const parts = fullKey.split(" ");
            return "Max " + parts.slice(1).join(" ");
        } else if (fullKey.startsWith("Max ")) {
            // Format: "Max Shungokusatsu" -> keep as is
            return fullKey;
        }
        return fullKey;
    }
}

document.addEventListener('DOMContentLoaded', () => {
    new StreetFighterGame();
});