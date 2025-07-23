class StreetFighterGame {
    // init
    
    constructor() {
        this.initializeState();
        this.initializeConstants();
        this.initializeEventListeners();
        this.initializeUI();
        this.initializeWebSocket();
    }

    initializeState() {
        this.socket = null;
        this.gameSettings = {
            difficulty: 1,
            player1: { character: 'Ken', outfit: 1, superArt: 1 },
            player2: { character: 'Ken', outfit: 1, superArt: 1 }
        };
        this.gameLoaded = false;
        this.serverReady = false;
        this.firstFrameReceived = false;

        this.keyState = {};
        this.inputHistory = [];
        this.maxInputHistory = 20;  // ~max length of move sequence
        this.movesByLength = {};
        this.allCombos = {};
        this.allSpecialMoves = {};

        this.currentCharacter = 'Ken';
        this.playerDirection = 'right';
        this.characterGrid = {
            activePlayer: 'p1',
            p1: { selected: false, character: null, outfit: null },
            p2: { selected: false, character: null, outfit: null }
        };
    }

    initializeConstants() {
        this.characters = [
            'Alex', 'Chun-Li', 'Dudley', 'Elena', 'Gouki',
            'Hugo', 'Ibuki', 'Ken', 'Makoto', 'Necro',
            'Oro', 'Q', 'Remy', 'Ryu', 'Sean',
            'Twelve', 'Urien', 'Yang', 'Yun'
        ];

        this.actions = {
            NONE: 0,
            LEFT: 1, LEFT_UP: 2, UP: 3, RIGHT_UP: 4,
            RIGHT: 5, RIGHT_DOWN: 6, DOWN: 7, LEFT_DOWN: 8,
            LIGHT_PUNCH: 9, MEDIUM_PUNCH: 10, HEAVY_PUNCH: 11,
            LIGHT_KICK: 12, MEDIUM_KICK: 13, HEAVY_KICK: 14,
            LP_LK: 15, MP_MK: 16, HP_HK: 17,
            SUPER_ART: 18, COMBO: 19
        };

        this.idxToMove = {
            0: "No-Move",
            1: "Left", 2: "Left+Up", 3: "Up", 4: "Up+Right",
            5: "Right", 6: "Right+Down", 7: "Down", 8: "Down+Left",
            9: "Low Punch", 10: "Medium Punch", 11: "High Punch",
            12: "Low Kick", 13: "Medium Kick", 14: "High Kick",
            15: "Low Punch+Low Kick", 16: "Medium Punch+Medium Kick", 17: "High Punch+High Kick"
        };

        this.numOutfitsPerCharacter = 6;
        this.animationDuration = 600;
    }

    initializeEventListeners() {
        const handleKeyEvent = (e, isDown) => {
            if (!this.gameLoaded) return;

            this.keyState[e.code] = isDown;
            const action = this.getActionFromKeys();
            
            this.sendMessage('player_action', { action, move: this.idxToMove[action] });
            
            if (action !== this.actions.NONE) {
                this.inputHistory.push({ action, time: Date.now() });
                
                if (this.inputHistory.length > this.maxInputHistory) {
                    this.inputHistory.shift();
                }
                
                const detectedMove = this.detectExtra();
                if (detectedMove) {
                    this.sendMessage('player_action', { 
                        action: detectedMove.type === 'super_art' ? 18 : 19,
                        [detectedMove.type === 'super_art' ? 'super_art' : 'combo']: detectedMove.name
                    });
                }
            }
            
            e.preventDefault();
        };

        document.addEventListener('keydown', (e) => handleKeyEvent(e, true));
        document.addEventListener('keyup', (e) => handleKeyEvent(e, false));

        ['p1', 'p2'].forEach(player => {
            document.getElementById(`${player}-selected-portrait`).addEventListener('click', () => {
                this.switchActivePlayer(player);
            });
        });

        document.getElementById('start-game-btn').addEventListener('click', () => this.startGame());
        document.getElementById('play-again-btn').addEventListener('click', () => {
            this.resetSelections();
            this.showScreen('settings');
        });
        document.getElementById('error-back-btn').addEventListener('click', () => {
            this.showScreen('settings');
        });
    }

    initializeUI() {
        this.initializeCharacterGrid();
        this.initializeDifficultySlider();
        this.loadExtraMovesDisplay();
        this.showScreen('settings');
    }

    initializeCharacterGrid() {
        const gridContainer = document.getElementById('character-grid');
        gridContainer.innerHTML = '';
        
        this.characters.forEach((character, index) => {
            const portrait = this.createPortrait(character, index, 'character');
            gridContainer.appendChild(portrait);
        });
        
        this.updatePlayerBoxes();
        this.updateCharacterBorders();
    }

    initializeDifficultySlider() {
        const slider = document.getElementById('difficulty-slider');
        const label = document.getElementById('difficulty-label');
        const difficultyLabels = ['', 'Very Easy', 'Easy', 'Medium', 'Hard', 'Very Hard', 'Expert', 'Master', 'Extreme'];
        
        slider.addEventListener('input', (e) => {
            const value = parseInt(e.target.value);
            this.gameSettings.difficulty = value;
            label.textContent = difficultyLabels[value];
        });
    }

    async loadExtraMovesDisplay() {
        const elements = {
            combosLoading: document.getElementById('combos-loading'),
            superArtsLoading: document.getElementById('super-arts-loading'),
            combosList: document.getElementById('combos-list'),
            superArtsList: document.getElementById('super-arts-list')
        };

        try {
            const response = await fetch('/api/extra-moves');
            const data = await response.json();
            this.allCombos = data.combos;
            this.allSpecialMoves = data.special_moves;
            
            this.preprocessMoves();
            this.updateCombosDisplay(this.currentCharacter);
            this.updateSuperArtsDisplay(this.currentCharacter);
            
            const superArtSelect = document.getElementById('super-art-select-p1');
            this.gameSettings.player1.superArt = parseInt(superArtSelect.value);
            
            superArtSelect.addEventListener('change', () => {
                this.gameSettings.player1.superArt = parseInt(superArtSelect.value);
                this.updateSuperArtsDisplay(this.currentCharacter);
                this.preprocessMoves();
            });
            
            elements.combosLoading.classList.add('hidden');
            elements.superArtsLoading.classList.add('hidden');
        } catch (error) {
            console.error('Failed to load combos:', error);
            elements.combosLoading.classList.add('hidden');
            elements.superArtsLoading.classList.add('hidden');
            elements.combosList.innerHTML = '<p class="text-sf-red">Failed to load combos</p>';
            elements.superArtsList.innerHTML = '<p class="text-sf-red">Failed to load super arts</p>';
        }
    }

    // ws

    initializeWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;
        
        this.socket = new WebSocket(wsUrl);
        const startButton = document.getElementById('start-game-btn');
        
        this.socket.onopen = () => console.log('Connected to server');
        
        this.socket.onclose = () => {
            console.log('Disconnected from server');
            if (!this.serverReady) {
                startButton.textContent = 'Connection Lost';
                startButton.disabled = true;
                startButton.classList.add('opacity-50');
            }
        };
        
        this.socket.onerror = (event) => {
            console.error('WebSocket connection error', event);
            this.showError('WebSocket connection error');
            if (!this.serverReady) {
                startButton.textContent = 'Connection Error';
                startButton.disabled = true;
                startButton.classList.add('opacity-50');
            }
        };
        
        this.socket.onmessage = (event) => this.handleWebSocketMessage(event);
        
        startButton.disabled = true;
        startButton.classList.add('opacity-50');
    }

    async handleWebSocketMessage(event) {
        if (event.data instanceof Blob) {
            this.handleFrameData(event.data);
            return;
        }
        
        const message = JSON.parse(event.data);
        if (message.type === 'game_state') {
            this.handleGameState(message.data);
        }
    }

    handleFrameData(blob) {
        if (!this.firstFrameReceived) {
            this.firstFrameReceived = true;
            document.getElementById('canvas-loading-overlay').classList.add('hidden');
        }
        
        const canvas = document.getElementById('game-canvas');
        const ctx = canvas.getContext('2d');
        const url = URL.createObjectURL(blob);
        const img = new Image();
        
        img.onload = () => {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
            URL.revokeObjectURL(url);
        };
        img.src = url;
    }

    handleGameState(data) {
        console.log('Game state:', data.status);
        const startButton = document.getElementById('start-game-btn');

        if (!this.serverReady) {
            this.serverReady = true;
            startButton.disabled = false;
            startButton.textContent = 'START GAME';
            startButton.classList.remove('opacity-50');
            console.log('Server ready');
        }

        switch (data.status) {
            case 'initializing':
                document.getElementById('loading-status').textContent = 'Starting game...';
                break;
            case 'running':
                this.gameLoaded = true;
                this.showScreen('game');
                break;
            case 'finished':
                this.gameLoaded = false;
                document.getElementById('winner-text').textContent = `Winner: ${data.winner || 'Unknown'}`;
                this.showScreen('win');
                break;
            case 'error':
                this.showError(data.error || 'Unknown game error');
                break;
        }
    }

    sendMessage(type, data) {
        if (this.socket && this.socket.readyState === WebSocket.OPEN) {
            this.socket.send(JSON.stringify({
                type: type,
                data: data
            }));
        }
    }

    // game state

    startGame() {
        const { p1, p2 } = this.characterGrid;
        
        if (!p1.selected || !p2.selected) {
            alert('Both players must select a character before starting!');
            return;
        }

        if (!p1.outfit || !p2.outfit) {
            alert('Both players must select an outfit before starting!');
            return;
        }

        Object.assign(this.gameSettings.player1, {
            character: p1.character,
            outfit: p1.outfit,
            superArt: parseInt(document.getElementById('super-art-select-p1').value)
        });

        Object.assign(this.gameSettings.player2, {
            character: p2.character,
            outfit: p2.outfit,
            superArt: parseInt(document.getElementById('super-art-select-p2').value)
        });

        this.gameSettings.difficulty = parseInt(document.getElementById('difficulty-slider').value);

        this.resetGameState();
        this.showScreen('loading');
        document.getElementById('loading-status').textContent = 'Starting game...';
        this.sendMessage('start_game', this.gameSettings);
    }

    resetGameState() {
        this.gameLoaded = false;
        this.serverReady = false;
        this.firstFrameReceived = false;
        this.keyState = {};
        this.inputHistory = [];

        const canvas = document.getElementById('game-canvas');
        const ctx = canvas.getContext('2d');
        ctx.clearRect(0, 0, canvas.width, canvas.height);
    }

    // input handling

    preprocessMoves() {
        this.movesByLength = {};
        
        if (!this.currentCharacter) return;
        
        const characterMoves = this.allSpecialMoves[this.currentCharacter];
        const characterCombos = this.allCombos[this.currentCharacter];
        const selectedSuperArt = this.gameSettings.player1.superArt;
        
        if (characterMoves) {
            this.addMovesToLength(characterMoves, selectedSuperArt, 'super_art');
        }
        
        if (characterCombos) {
            for (const [comboName, comboData] of Object.entries(characterCombos)) {
                const seq = comboData[this.playerDirection];
                this.addMoveToLength(seq, 'combo', comboName);
            }
        }
        
        this.sortMovesByPriority();
    }

    addMovesToLength(moves, selectedSuperArt, moveType) {
        for (const [moveKey, moveData] of Object.entries(moves)) {
            if (this.isSuperArtMove(moveKey, selectedSuperArt)) {
                const seq = moveData[this.playerDirection];
                this.addMoveToLength(seq, moveType, moveKey);
            }
        }
    }

    isSuperArtMove(moveKey, selectedSuperArt) {
        return moveKey.startsWith(`${selectedSuperArt} `) ||
               (moveKey.startsWith("Max") && 
                (moveKey.startsWith(`Max-${selectedSuperArt} `) || moveKey.startsWith("Max ")));
    }

    addMoveToLength(sequence, type, name) {
        if (!this.movesByLength[sequence.length]) {
            this.movesByLength[sequence.length] = [];
        }
        this.movesByLength[sequence.length].push({ type, name, sequence });
    }

    sortMovesByPriority() {
        for (const length in this.movesByLength) {
            this.movesByLength[length].sort((a, b) => 
                a.type === 'super_art' && b.type === 'combo' ? -1 :
                a.type === 'combo' && b.type === 'super_art' ? 1 : 0
            );
        }
    }

    getActionFromKeys() {
        const attacks = {
            LP: this.keyState['KeyJ'],
            MP: this.keyState['KeyK'],
            HP: this.keyState['KeyL'],
            LK: this.keyState['KeyU'],
            MK: this.keyState['KeyI'],
            HK: this.keyState['KeyO']
        };

        if (attacks.LP && attacks.LK) return this.actions.LP_LK;
        if (attacks.MP && attacks.MK) return this.actions.MP_MK;
        if (attacks.HP && attacks.HK) return this.actions.HP_HK;

        if (attacks.HP) return this.actions.HEAVY_PUNCH;
        if (attacks.MP) return this.actions.MEDIUM_PUNCH;
        if (attacks.LP) return this.actions.LIGHT_PUNCH;
        if (attacks.HK) return this.actions.HEAVY_KICK;
        if (attacks.MK) return this.actions.MEDIUM_KICK;
        if (attacks.LK) return this.actions.LIGHT_KICK;

        const directions = {
            left: this.keyState['KeyA'] || this.keyState['ArrowLeft'],
            right: this.keyState['KeyD'] || this.keyState['ArrowRight'],
            up: this.keyState['KeyW'] || this.keyState['ArrowUp'],
            down: this.keyState['KeyS'] || this.keyState['ArrowDown']
        };

        if (directions.left && directions.up) return this.actions.LEFT_UP;
        if (directions.right && directions.up) return this.actions.RIGHT_UP;
        if (directions.left && directions.down) return this.actions.LEFT_DOWN;
        if (directions.right && directions.down) return this.actions.RIGHT_DOWN;

        if (directions.left) return this.actions.LEFT;
        if (directions.right) return this.actions.RIGHT;
        if (directions.up) return this.actions.UP;
        if (directions.down) return this.actions.DOWN;

        return this.actions.NONE;
    }

    detectExtra() {
        const comboTimeout = 500; // ms
        const currentTime = Date.now();

        this.inputHistory = this.inputHistory.filter(input => 
            currentTime - input.time <= comboTimeout
        );
        
        if (this.inputHistory.length < 2) return null;
        
        for (let len = this.inputHistory.length; len >= 2; len--) {
            const match = this.findMoveMatch(len);
            if (match) {
                this.inputHistory = [];
                return match;
            }
        }
        
        return null;
    }

    findMoveMatch(sequenceLength) {
        const moves = this.movesByLength[sequenceLength];
        if (!moves) return null;
        
        const startIndex = this.inputHistory.length - sequenceLength;
        
        for (const move of moves) {
            if (this.isSequenceMatch(move.sequence, startIndex)) {
                return { type: move.type, name: move.name };
            }
        }
        
        return null;
    }

    isSequenceMatch(sequence, startIndex) {
        for (let i = 0; i < sequence.length; i++) {
            if (this.inputHistory[startIndex + i].action !== sequence[i]) {
                return false;
            }
        }
        return true;
    }

    // ui

    showScreen(screenId) {
        const screens = [
            { id: 'settings-screen', show: screenId === 'settings' },
            { id: 'loading-screen', show: screenId === 'loading' },
            { id: 'game-display', show: screenId === 'game' },
            { id: 'win-screen', show: screenId === 'win' },
            { id: 'error-screen', show: screenId === 'error' }
        ];
        screens.forEach(screen => {
            const el = document.getElementById(screen.id);
            if (el) {
                if (screen.show) {
                    el.classList.remove('hidden');
                } else {
                    el.classList.add('hidden');
                }
            }
        });
        
        const header = document.getElementById('game-header');
        if (header) {
            if (screenId === 'game') {
                header.classList.add('hidden');
            } else {
                header.classList.remove('hidden');
            }
        }
    }

    showError(message) {
        document.getElementById('error-details').textContent = new Date().toLocaleString() + '\n' + message;
        this.showScreen('error');
    }

    // character move display

    updateCombosDisplay(character) {
        const combosList = document.getElementById('combos-list');
        const combos = this.allCombos[character];
        
        const moves = Object.entries(combos).map(([name, data]) => ({
            name,
            sequence: data[this.playerDirection]
        }));
        
        combosList.innerHTML = this.generateMovesHTML(moves);
    }
    
    updateSuperArtsDisplay(character) {
        const superArtsList = document.getElementById('super-arts-list');
        const selectedSuperArt = document.getElementById('super-art-select-p1').value;
        const characterMoves = this.allSpecialMoves[character];
        const moves = [];
        
        for (const [moveKey, moveData] of Object.entries(characterMoves)) {
            if (moveKey.startsWith(`${selectedSuperArt} `)) {
                moves.push({
                    name: this.getSpecialMoveDisplayName(moveKey),
                    sequence: moveData[this.playerDirection]
                });
                break;
            }
        }
        
        for (const [moveKey, moveData] of Object.entries(characterMoves)) {
            if (typeof moveKey === 'string' && moveKey.startsWith("Max")) {
                if (moveKey.startsWith(`Max-${selectedSuperArt} `) || moveKey.startsWith("Max ")) {
                    moves.push({
                        name: this.getSpecialMoveDisplayName(moveKey),
                        sequence: moveData[this.playerDirection]
                    });
                }
            }
        }
        
        superArtsList.innerHTML = this.generateMovesHTML(moves);
    }
    
    generateMovesHTML(moves) {
        const moveElements = moves.map(move => `
            <p>${move.name}:</p>
            <div class="flex items-center gap-2 flex-wrap justify-center mb-4">
                ${this.getExtraElements(move.sequence)}
            </div>
        `).join('');
        
        return `<div class="text-center flex flex-col justify-center items-center gap-4">${moveElements}</div>`;
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
                <span class="control-key">${symbol}</span>
                ${!isLast ? '<span>+</span>' : ''}
            `;
        }).join('');
    }
    
    getSpecialMoveDisplayName(fullKey) {
        if (fullKey.match(/^\d+ /)) {
            // format: "1 Messatsu Gou Hadou" -> "Messatsu Gou Hadou"
            return fullKey.substring(2);
        } else if (fullKey.startsWith("Max-")) {
            // format: "Max-1 Messatsu Gou Hadou" -> "Max Messatsu Gou Hadou"
            const parts = fullKey.split(" ");
            return "Max " + parts.slice(1).join(" ");
        }
        return fullKey;
    }

    // character/outfit display

    switchActivePlayer(player) {
        this.characterGrid.activePlayer = player;
        this.updatePlayerBoxes();
        this.updateCharacterBorders();
        
        const selectedCharacter = this.characterGrid[player].character;
        if (selectedCharacter) {
            this.initializeOutfitGrid(selectedCharacter);
        } else {
            document.getElementById('outfit-selection').classList.add('hidden');
        }
    }
    
    updatePlayerBoxes() {
        const p1Portrait = document.getElementById('p1-selected-portrait');
        const p2Portrait = document.getElementById('p2-selected-portrait');
        const activeColor = this.getPlayerColor(this.characterGrid.activePlayer);
        
        p1Portrait.className = `portrait-box border-${this.characterGrid.activePlayer === 'p1' ? activeColor : 'transparent'}`;
        p2Portrait.className = `portrait-box border-${this.characterGrid.activePlayer === 'p2' ? activeColor : 'transparent'}`;
    }
    
    updateCharacterBorders() {
        const portraits = document.querySelectorAll('#character-grid > div');
        
        portraits.forEach(el => {
            el.classList.remove('border-sf-red', 'border-sf-blue');
            el.classList.add('border-transparent');
        });
        
        ['p1', 'p2'].forEach(player => {
            if (this.characterGrid[player].character) {
                const selected = Array.from(portraits).find(p => p.dataset.character === this.characterGrid[player].character);
                if (selected) {
                    selected.classList.remove('border-transparent');
                    selected.classList.add(`border-${this.getPlayerColor(player)}`);
                }
            }
        });
    }
    
    selectCharacter(player, character) {
        if (!character) return;
        
        const portraits = document.querySelectorAll('#character-grid > div');
        const selectedPortrait = Array.from(portraits).find(p => p.dataset.character === character);
        if (!selectedPortrait) return;
        
        selectedPortrait.classList.add('animate-character-flash');
        
        setTimeout(() => {
            selectedPortrait.classList.remove('animate-character-flash');
            
            this.characterGrid[player].selected = true;
            this.characterGrid[player].character = character;
            
            if (player === 'p1') {
                this.currentCharacter = character;
                this.updateCombosDisplay(character);
                this.updateSuperArtsDisplay(character);
                this.preprocessMoves();
            }
            
            this.updatePlayerPortrait(player, character);
            this.updateCharacterBorders();
            this.initializeOutfitGrid(character);
            document.getElementById('outfit-selection').classList.remove('hidden');
        }, this.animationDuration);
    }

    updatePlayerPortrait(player, character) {
        const portraitImg = document.querySelector(`#${player}-selected-portrait img`);
        const nameEl = document.getElementById(`${player}-selected-name`);
        const portraitBox = document.getElementById(`${player}-selected-portrait`);
        
        const existingPlaceholder = portraitBox.querySelector('.portrait-placeholder');
        if (existingPlaceholder) existingPlaceholder.remove();
        
        const placeholder = document.createElement('div');
        placeholder.className = 'portrait-placeholder absolute inset-0 loading-placeholder rounded-lg';
        portraitBox.appendChild(placeholder);
        
        portraitImg.classList.add('opacity-0');
        portraitImg.src = `/portraits/${character}.png`;
        portraitImg.classList.remove('hidden');
        nameEl.textContent = character;
        
        const loadHandler = () => {
            portraitImg.classList.remove('opacity-0');
            portraitImg.classList.add('opacity-100', 'transition-opacity', 'duration-300');
            const ph = portraitBox.querySelector('.portrait-placeholder');
            if (ph) ph.remove();
        };
        
        const errorHandler = () => {
            portraitImg.classList.remove('opacity-0');
            portraitImg.classList.add('opacity-100');
            const ph = portraitBox.querySelector('.portrait-placeholder');
            if (ph) ph.innerHTML = '<div class="flex items-center justify-center h-full text-sf-red">?</div>';
        };
        
        portraitImg.addEventListener('load', loadHandler, { once: true });
        portraitImg.addEventListener('error', errorHandler, { once: true });
    }

    selectOutfit(player, outfitIndex) {
        const outfitNum = outfitIndex + 1;  // 1-based for display
        
        const outfits = document.querySelectorAll('#outfit-grid > div');
        const selectedOutfit = outfits[outfitIndex];
        if (!selectedOutfit) return;
        
        selectedOutfit.classList.add('animate-character-flash');
        
        setTimeout(() => {
            selectedOutfit.classList.remove('animate-character-flash');
            this.characterGrid[player].outfit = outfitNum;
            this.updateOutfitBorders();
        }, this.animationDuration);
    }
    
    updateOutfitBorders() {
        const outfits = document.querySelectorAll('#outfit-grid > div');
        const activePlayer = this.characterGrid.activePlayer;
        const selectedOutfit = this.characterGrid[activePlayer].outfit;
        const borderColor = `border-${this.getPlayerColor(activePlayer)}`;
        
        outfits.forEach((el, index) => {
            el.classList.remove('border-sf-red', 'border-sf-blue');
            if (selectedOutfit && selectedOutfit === index + 1) {
                el.classList.remove('border-transparent');
                el.classList.add(borderColor);
            } else {
                el.classList.add('border-transparent');
            }
        });
    }

    initializeOutfitGrid(character) {
        const gridContainer = document.getElementById('outfit-grid');
        const indicator = document.getElementById('outfit-player-indicator');
        
        const activePlayer = this.characterGrid.activePlayer;
        const colorClass = `text-${this.getPlayerColor(activePlayer)}`;
        indicator.innerHTML = `<span class="${colorClass}">${this.getPlayerText(activePlayer)}</span> - ${character} Outfits`;
        
        gridContainer.innerHTML = '';

        for (let i = 0; i < this.numOutfitsPerCharacter; i++) {
            const outfit = this.createOutfitBox(character, i);
            gridContainer.appendChild(outfit);
        }
        
        this.updateOutfitBorders();
    }

    // ui element creation
    
    createOutfitBox(character, index) {
        const outfit = this.createImageBox({
            className: 'relative size-24 bg-sf-dark border-2 border-transparent rounded-lg hover:scale-105 cursor-pointer transition-all duration-200 mx-auto',
            imageSrc: `/outfits/${character}/${index}.png`,
            imageAlt: `Outfit ${index + 1}`,
            imageClassName: 'relative size-full object-contain bg-sf-dark rounded-lg'
        });
        
        outfit.dataset.outfit = index;
        
        const label = document.createElement('div');
        label.className = 'absolute bottom-0 left-0 right-0 p-1 text-center font-bold text-sf-green bg-sf-darker/80 backdrop-blur-sm rounded-b-lg';
        label.textContent = `${index + 1}`;
        outfit.appendChild(label);
        
        const borderColor = `border-${this.getPlayerColor(this.characterGrid.activePlayer)}`;
        
        outfit.addEventListener('mouseenter', () => {
            if (!outfit.classList.contains('border-sf-red') && !outfit.classList.contains('border-sf-blue')) {
                outfit.classList.remove('border-transparent');
                outfit.classList.add(borderColor);
            }
        });
        
        outfit.addEventListener('mouseleave', () => {
            const activePlayer = this.characterGrid.activePlayer;
            const isSelected = this.characterGrid[activePlayer].outfit === index + 1;
            if (!isSelected) {
                outfit.classList.remove('border-sf-red', 'border-sf-blue');
                outfit.classList.add('border-transparent');
            }
        });
        
        outfit.addEventListener('click', () => {
            this.selectOutfit(this.characterGrid.activePlayer, index);
        });
        
        return outfit;
    }

    createPortrait(character, index, type) {
        const portrait = this.createImageBox({
            className: 'relative w-full aspect-square bg-sf-dark border-2 border-transparent rounded-lg hover:scale-105 cursor-pointer transition-all duration-200',
            imageSrc: `/portraits/${character}.png`,
            imageAlt: character,
            imageClassName: 'relative w-full h-full object-contain rounded-lg'
        });
        
        portrait.dataset.character = character;
        portrait.dataset.index = index;
        
        const nameLabel = document.createElement('div');
        nameLabel.className = 'absolute bottom-0 left-0 right-0 p-1 text-center font-bold text-sf-green bg-sf-darker/80 backdrop-blur-sm rounded-b-lg';
        nameLabel.textContent = character;
        portrait.appendChild(nameLabel);
        
        portrait.addEventListener('mouseenter', () => {
            if (type === 'character') {
                const borderColor = `border-${this.getPlayerColor(this.characterGrid.activePlayer)}`;
                portrait.classList.remove('border-transparent');
                portrait.classList.add(borderColor);
            }
        });
        
        portrait.addEventListener('mouseleave', () => {
            portrait.classList.remove('border-sf-red', 'border-sf-blue');
            portrait.classList.add('border-transparent');
            this.updateCharacterBorders();
        });
        
        portrait.addEventListener('click', () => {
            this.selectCharacter(this.characterGrid.activePlayer, character);
        });
        
        return portrait;
    }

    createImageBox({ className, imageSrc, imageAlt, imageClassName }) {
        const box = document.createElement('div');
        box.className = className;
        
        const placeholder = document.createElement('div');
        placeholder.className = 'absolute inset-0 loading-placeholder rounded-lg';
        box.appendChild(placeholder);
        
        const img = document.createElement('img');
        img.src = imageSrc;
        img.alt = imageAlt;
        img.className = imageClassName + ' opacity-0 transition-opacity duration-300';
        
        img.addEventListener('load', () => {
            img.classList.remove('opacity-0');
            img.classList.add('opacity-100');
            placeholder.remove();
        }, { once: true });
        
        img.addEventListener('error', () => {
            img.classList.remove('opacity-0');
            img.classList.add('opacity-100');
            placeholder.innerHTML = '<div class="flex items-center justify-center h-full text-sf-red">?</div>';
        }, { once: true });
        
        box.appendChild(img);
        return box;
    }

    // utility fns

    getPlayerColor(player) {
        return player === 'p1' ? 'sf-red' : 'sf-blue';
    }

    getPlayerText(player) {
        return player === 'p1' ? 'Player 1' : 'Player 2';
    }

    resetSelections() {
        this.characterGrid = {
            activePlayer: 'p1',
            p1: { selected: false, character: null, outfit: null },
            p2: { selected: false, character: null, outfit: null }
        };
        
        this.currentCharacter = 'Ken';
        
        const p1Img = document.querySelector('#p1-selected-portrait img');
        const p2Img = document.querySelector('#p2-selected-portrait img');
        
        p1Img.src = '';
        p1Img.classList.add('hidden');
        p2Img.src = '';
        p2Img.classList.add('hidden');
        
        document.getElementById('p1-selected-name').textContent = '-';
        document.getElementById('p2-selected-name').textContent = '-';
        
        document.getElementById('outfit-selection').classList.add('hidden');
        
        document.getElementById('super-art-select-p1').value = '1';
        document.getElementById('super-art-select-p2').value = '1';
        this.gameSettings.player1.superArt = 1;
        this.gameSettings.player2.superArt = 1;
        
        if (this.currentCharacter && this.allCombos && this.allSpecialMoves) {
            this.updateCombosDisplay(this.currentCharacter);
            this.updateSuperArtsDisplay(this.currentCharacter);
            this.preprocessMoves();
        }
        
        document.getElementById('difficulty-slider').value = '1';
        document.getElementById('difficulty-label').textContent = 'Very Easy';
        this.gameSettings.difficulty = 1;
        
        this.updatePlayerBoxes();
        this.updateCharacterBorders();
    }
}

document.addEventListener('DOMContentLoaded', () => {
    new StreetFighterGame();
});