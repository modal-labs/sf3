class StreetFighterGame {

    // helper fns

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
        
        // show/hide header based on game state

        const header = document.getElementById('game-header');
        if (header) {
            if (game !== 'none') {
                header.classList.add('hidden');
            } else {
                header.classList.remove('hidden');
            }
        }
    };

    sendMessage(type, data) {
        if (this.socket && this.socket.readyState === WebSocket.OPEN) {
            this.socket.send(JSON.stringify({
                type: type,
                data: data
            }));
        }
    }

    showError(message) {
        document.getElementById('error-message').textContent = message;
        document.getElementById('error-details').textContent = new Date().toLocaleString() + '\n' + message;
        this.setScreen('none', 'none', 'none', 'none', 'block');
    }

    getActionFromKeys() {
        if (this.keyState['KeyP']) return this.actions.SUPER_ART;
        
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

    sendAction(action) {
        this.sendMessage('player_action', { action: action });
    }

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

    constructor() {
        this.socket = null;

        // game state

        this.gameLoaded = false;
        this.keyState = {};
        this.firstFrameReceived = false;
        this.renderLoopStarted = false;
        this.frameQueue = [];
        this.lastFrameTime = 0;
        this.targetFPS = 60;
        this.frameInterval = 1000 / this.targetFPS;
        this.serverReady = false;
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
            
            // super art
            SUPER_ART: 18
        };
    
        // event listeners

        const handleKeyEvent = (e, isDown) => {
            if (!this.gameLoaded) return;

            this.keyState[e.code] = isDown;
            const action = this.getActionFromKeys();
            this.sendAction(action);
            e.preventDefault();
        };

        document.addEventListener('keydown', (e) => handleKeyEvent(e, true));
        document.addEventListener('keyup', (e) => handleKeyEvent(e, false));

        // ui

        this.setScreen('block', 'none', 'none', 'none', 'none');

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

        const startButton = document.getElementById('start-game-btn');
        const playAgainButton = document.getElementById('play-again-btn');
        const errorBackButton = document.getElementById('error-back-btn');

        playAgainButton.addEventListener('click', () => {
            this.setScreen('block', 'none', 'none', 'none', 'none');
        });
        errorBackButton.addEventListener('click', () => {
            this.setScreen('block', 'none', 'none', 'none', 'none');
        });

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
                        console.log('Server ready - start button enabled');
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
            this.firstFrameReceived = false;
            this.renderLoopStarted = false;
            this.frameQueue = [];
            this.lastFrameTime = 0;
            this.keyState = {};
            const canvas = document.getElementById('game-canvas');
            const ctx = canvas.getContext('2d');
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            this.setScreen('none', 'block', 'none', 'none', 'none');

            document.getElementById('loading-status').textContent = 'Starting game...';
            
            // send start game message

            this.sendMessage('start_game', this.gameSettings);
        };

        startButton.addEventListener('click', startGame);
        startButton.disabled = true;
        startButton.classList.add('opacity-50');
    }
}

document.addEventListener('DOMContentLoaded', () => {
    new StreetFighterGame();
});