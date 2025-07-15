class StreetFighterGame {
    constructor() {
        this.socket = null;

        // game state

        this.gameLoaded = false;
        this.keyState = {};
        this.lastAction = 0;
        this.firstFrameReceived = false;
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
            // Basic actions
            NONE: 0,
            // Directional
            LEFT: 1,
            LEFT_UP: 2,
            UP: 3,
            RIGHT_UP: 4,
            RIGHT: 5,
            RIGHT_DOWN: 6,
            DOWN: 7,
            LEFT_DOWN: 8,
            // Attacks
            LIGHT_PUNCH: 9,
            MEDIUM_PUNCH: 10,
            HEAVY_PUNCH: 11,
            LIGHT_KICK: 12,
            MEDIUM_KICK: 13,
            HEAVY_KICK: 14,
            // Combinations
            LP_LK: 15,
            MP_MK: 16,
            HP_HK: 17
        };
    
        // event listeners

        document.addEventListener('keydown', (e) => {
            if (!this.gameLoaded) return;
            
            this.keyState[e.code] = true;
            const action = this.getActionFromKeys();
            if (action !== this.lastAction) {
                this.sendAction(action);
                this.lastAction = action;
            }
            e.preventDefault();
        });
        document.addEventListener('keyup', (e) => {
            if (!this.gameLoaded) return;
            
            this.keyState[e.code] = false;
            const action = this.getActionFromKeys();
            if (action !== this.lastAction) {
                this.sendAction(action);
                this.lastAction = action;
            }
            e.preventDefault();
        });
        
        // ui

        document.getElementById('settings-screen').style.display = 'block';
        document.getElementById('loading-screen').style.display = 'none';
        document.getElementById('game-display').style.display = 'none';
        document.getElementById('win-screen').style.display = 'none';
        document.getElementById('error-screen').style.display = 'none';

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

        // main game logic

        const startButton = document.getElementById('start-game-btn');
        const playAgainButton = document.getElementById('play-again-btn');
        
        const startGame = () => {
            this.gameSettings.player1.character = document.getElementById('character-select').value;
            this.gameSettings.player1.outfit = parseInt(document.getElementById('outfit-select').value);
            this.gameSettings.player1.superArt = parseInt(document.getElementById('super-art-select').value);
            this.gameSettings.player2.character = document.getElementById('character-select-p2').value;
            this.gameSettings.player2.outfit = parseInt(document.getElementById('outfit-select-p2').value);
            this.gameSettings.player2.superArt = parseInt(document.getElementById('super-art-select-p2').value);
            this.gameSettings.difficulty = parseInt(document.getElementById('difficulty-slider').value);
            console.log('Game settings:', this.gameSettings);

            this.firstFrameReceived = false;
            const canvas = document.getElementById('game-canvas');
            const ctx = canvas.getContext('2d');
            ctx.clearRect(0, 0, canvas.width, canvas.height);

            document.getElementById('settings-screen').style.display = 'none';
            document.getElementById('loading-screen').style.display = 'block';
            document.getElementById('game-display').style.display = 'none';
            document.getElementById('win-screen').style.display = 'none';
            document.getElementById('error-screen').style.display = 'none';

            let msg = 'Connecting to server...';
            console.log(msg);
            document.getElementById('loading-status').textContent = msg;
            
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/ws`;
            
            this.socket = new WebSocket(wsUrl);
            
            this.socket.onopen = () => {
                msg = 'Connected to server; starting emulator...';
                console.log(msg);
                document.getElementById('loading-status').textContent = msg;
                this.sendMessage('start_game', this.gameSettings);
            };
            
            this.socket.onclose = () => {
                console.log('Disconnected from server');
            };
            
            this.socket.onerror = (event) => {
                let errorMsg = 'WebSocket connection error';
                if (event && event.message) {
                    errorMsg += ': ' + event.message;
                }
                console.error(errorMsg, event);
                this.showError(errorMsg);
            };
            
            this.socket.onmessage = (event) => {
                const message = JSON.parse(event.data);
                
                switch (message.type) {
                    case 'game_state':
                        console.log('Game state:', message.data.status);
        
                        switch (message.data.status) {
                            case 'initializing':
                                document.getElementById('loading-status').textContent = 'Initializing game environment...';
                                break;
                            case 'running':
                                if (!this.gameLoaded) {
                                    this.gameLoaded = true;
                                    document.getElementById('settings-screen').style.display = 'none';
                                    document.getElementById('loading-screen').style.display = 'none';
                                    document.getElementById('game-display').style.display = 'block';
                                    document.getElementById('win-screen').style.display = 'none';
                                    document.getElementById('canvas-loading-overlay').style.display = 'flex';
                                }
                                break;
                            case 'finished':
                                this.gameLoaded = false;
                                document.getElementById('winner-text').textContent = `Winner: ${message.data.winner || 'Unknown'}`;
                                document.getElementById('settings-screen').style.display = 'none';
                                document.getElementById('loading-screen').style.display = 'none';
                                document.getElementById('game-display').style.display = 'none';
                                document.getElementById('win-screen').style.display = 'block';
                                break;
                            case 'error':
                                this.showError(message.data.error || 'Unknown game error');
                                if (this.socket) {
                                    this.socket.close();
                                    this.socket = null;
                                }
                                break;
                        }
                        break;
                    case 'game_frame':
                        const canvas = document.getElementById('game-canvas');
                        const ctx = canvas.getContext('2d');
                        
                        const img = new Image();
                        img.onload = () => {
                            ctx.clearRect(0, 0, canvas.width, canvas.height);
                            ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
                            
                            if (!this.firstFrameReceived) {
                                this.firstFrameReceived = true;
                                document.getElementById('canvas-loading-overlay').style.display = 'none';
                            }
                        };
                        img.src = 'data:image/jpeg;base64,' + message.data.frame;
                        break;
                }
            };
        };
        
        startButton.addEventListener('click', startGame);
        playAgainButton.addEventListener('click', () => {
            document.getElementById('settings-screen').style.display = 'block';
            document.getElementById('loading-screen').style.display = 'none';
            document.getElementById('game-display').style.display = 'none';
            document.getElementById('win-screen').style.display = 'none';
        });

        const errorBackButton = document.getElementById('error-back-btn');
        errorBackButton.addEventListener('click', () => {
            document.getElementById('settings-screen').style.display = 'block';
            document.getElementById('loading-screen').style.display = 'none';
            document.getElementById('game-display').style.display = 'none';
            document.getElementById('win-screen').style.display = 'none';
            document.getElementById('error-screen').style.display = 'none';
        });

    }

    // helper fns

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
        document.getElementById('settings-screen').style.display = 'none';
        document.getElementById('loading-screen').style.display = 'none';
        document.getElementById('game-display').style.display = 'none';
        document.getElementById('win-screen').style.display = 'none';
        document.getElementById('error-screen').style.display = 'block';
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

    sendAction(action) {
        this.sendMessage('player_action', { action: action });
    }

}

document.addEventListener('DOMContentLoaded', () => {
    new StreetFighterGame();
});