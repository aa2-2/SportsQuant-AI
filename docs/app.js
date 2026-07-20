// MLBQuant Interactive Dashboard - Real Data Version
document.addEventListener('DOMContentLoaded', function() {
    // DOM Elements
    const sidebar = document.getElementById('sidebar');
    const sidebarToggle = document.getElementById('sidebarToggle');
    const sidebarClose = document.getElementById('sidebarClose');
    const overlay = document.getElementById('overlay');
    const mainContent = document.querySelector('.main-content');
    const dateFilter = document.getElementById('dateFilter');
    const searchFilter = document.getElementById('searchFilter');
    const gamesGrid = document.getElementById('gamesGrid');
    const todayBtn = document.getElementById('todayBtn');
    const seasonBtn = document.getElementById('seasonBtn');

    // Stats elements
    const totalGamesEl = document.getElementById('totalGames');
    const barrelPctEl = document.getElementById('barrelPct');
    const avgExitVeloEl = document.getElementById('avgExitVelo');
    const hrWeatherImpactEl = document.getElementById('hrWeatherImpact');

    // Data storage
    let gamesData = [];
    let statcastData = {};
    let weatherImpactData = [];
    let batterLeadersData = {};
    let batterStatsData = {};

    // Initialize
    init();

    async function init() {
        await loadData();
        updateStats();
        renderGames();
        renderBatterLeaders(); // Render batter leaders
        setupEventListeners();
    }

    async function loadData() {
        try {
            // Fetch all JSON data files
            const [gamesResp, statsResp, weatherResp, batterLeadersResp, batterStatsResp] = await Promise.all([
                fetch('/data/recent_games.json'),
                fetch('/data/statcast_summary.json'),
                fetch('/data/weather_impact.json'),
                fetch('/data/batter_leaders.json'),
                fetch('/data/batter_stats.json')
            ]);

            gamesData = await gamesResp.json();
            statcastData = await statsResp.json();
            weatherImpactData = await weatherResp.json();
            batterLeadersData = await batterLeadersResp.json();
            batterStatsData = await batterStatsResp.json();

            console.log('Data loaded:', {
                games: gamesData.length,
                stats: statcastData,
                weather: weatherImpactData.length,
                batterLeaders: batterLeadersData.total_batters,
                batterStats: batterStatsData
            });
        } catch (error) {
            console.error('Failed to load data:', error);
            // Fallback to empty arrays/objects
            gamesData = [];
            statcastData = {};
            weatherImpactData = [];
            batterLeadersData = {};
            batterStatsData = {};
        }
    }

    function updateStats() {
        // Update stats cards with real data
        if (totalGamesEl) totalGamesEl.textContent = gamesData.length;
        if (barrelPctEl) barrelPctEl.textContent = (statcastData.barrel_percentage || 0) + '%';
        if (avgExitVeloEl) avgExitVeloEl.textContent = (statcastData.avg_exit_velocity || 0) + ' mph';
        if (hrWeatherImpactEl) {
            // Calculate average weather impact from available data
            const impacts = weatherImpactData.map(w =>
                parseFloat(w.hr_weather_adjustment) || 0
            );
            const avgImpact = impacts.reduce((a, b) => a + b, 0) / Math.max(impacts.length, 1);
            hrWeatherImpactEl.textContent = (avgImpact >= 0 ? '+' : '') + avgImpact.toFixed(1) + '%';
            hrWeatherImpactEl.className = 'stat-value' + (avgImpact >= 0 ? ' positive' : ' negative');
        }

        // Update new stats elements from batter data
        const totalBattersEl = document.getElementById('totalBatters');
        const avgBarrelPctEl = document.getElementById('avgBarrelPct');
        const avgXHREl = document.getElementById('avgXHR');
        const topBatterXHREl = document.getElementById('topBatterXHR');

        if (totalBattersEl && batterStatsData.total_batters) {
            totalBattersEl.textContent = batterStatsData.total_batters.toLocaleString();
        }
        if (avgBarrelPctEl && batterStatsData.avg_barrel_pct !== undefined) {
            avgBarrelPctEl.textContent = batterStatsData.avg_barrel_pct.toFixed(2) + '%';
        }
        if (avgXHREl && batterStatsData.avg_xhr_pct !== undefined) {
            avgXHREl.textContent = batterStatsData.avg_xhr_pct.toFixed(2) + '%';
        }
        if (topBatterXHREl && batterLeadersData.batters && batterLeadersData.batters.length > 0) {
            const topBatter = batterLeadersData.batters[0];
            topBatterXHREl.textContent = topBatter.player_name + ' (' + topBatter.xhr_pct_season.toFixed(1) + '%)';
        }
    }

    function renderGames() {
        if (!gamesGrid) return;

        // Filter games based on current filters
        const filteredGames = filterGames(gamesData);

        // Take first 6 games for display (or all if less than 6)
        const displayGames = filteredGames.slice(0, 6);

        if (displayGames.length === 0) {
            gamesGrid.innerHTML = '<p class="no-data">No games found matching your filters.</p>';
            return;
        }

        gamesGrid.innerHTML = displayGames.map(game => createGameCard(game)).join('');
    }

    function filterGames(games) {
        const dateValue = dateFilter ? dateFilter.value : '';
        const searchValue = searchFilter ? searchFilter.value.toLowerCase() : '';

        return games.filter(game => {
            // Date filter
            const dateMatch = dateValue === 'today' ?
                game.date === new Date().toISOString().split('T')[0] :
                dateValue === 'tomorrow' ?
                game.date === new Date(Date.now() + 86400000).toISOString().split('T')[0] :
                dateValue === 'this_week' ?
                isThisWeek(game.date) :
                true; // 'all' or empty

            // Search filter
            const searchMatch = searchValue === '' ||
                game.away_team.toLowerCase().includes(searchValue) ||
                game.home_team.toLowerCase().includes(searchValue);

            return dateMatch && searchMatch;
        });
    }

    function isThisWeek(dateString) {
        const today = new Date();
        const gameDate = new Date(dateString);
        const startOfWeek = new Date(today);
        startOfWeek.setDate(today.getDate() - today.getDay()); // Sunday
        startOfWeek.setHours(0, 0, 0, 0);

        const endOfWeek = new Date(startOfWeek);
        endOfWeek.setDate(startOfWeek.getDate() + 6); // Saturday
        endOfWeek.setHours(23, 59, 59, 999);

        return gameDate >= startOfWeek && gameDate <= endOfWeek;
    }

    function createGameCard(game) {
        const hrImpactClass = parseFloat(game.hr_weather_adjustment || 0) >= 0 ? 'positive' : 'negative';
        const hrImpactSign = parseFloat(game.hr_weather_adjustment || 0) >= 0 ? '+' : '';

        return `
            <div class="game-card" data-id="${game.game_pk}">
                <div class="game-header">
                    <div class="teams">
                        <div class="team-logo">
                            <img src="https://img.mlbstatic.com/mlb-logos/${game.away_team.toLowerCase().replace(' ', '-')}.svg"
                                 alt="${game.away_team}" onerror="this.src='https://img.mlbstatic.com/mlb-logo.svg'">
                        </div>
                        <div class="team-info">
                            <div class="team-name">${game.away_team}</div>
                            <div class="team-record">${game.away_team}</div>
                        </div>
                    </div>
                    <div class="versus">@</div>
                    <div class="team-info">
                        <div class="team-name">${game.home_team}</div>
                        <div class="team-record">${game.home_team}</div>
                    </div>
                    <div class="game-time">${formatTime(game.date)}</div>
                </div>
                <div class="game-body">
                    <div class="game-info">
                        <div class="info-item">
                            <span class="info-label">Venue</span>
                            <span class="info-value">TBD</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">Roof</span>
                            <span class="info-value">Open</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">Weather</span>
                            <span class="info-value">${game.weather_main || 'Clear'}</span>
                        </div>
                    </div>
                    <div class="weather-stats">
                        <div class="stat-column">
                            <div class="stat-label">TEMP</div>
                            <div class="stat-value">${game.temp_f || 'N/A'}</div>
                        </div>
                        <div class="stat-column">
                            <div class="stat-label">HUMIDITY</div>
                            <div class="stat-value">65%</div>
                        </div>
                    </div>
                    <div class="weather-stats">
                        <div class="stat-column">
                            <div class="stat-label">WIND</div>
                            <div class="stat-value">${game.wind_display || 'Calm'}</div>
                        </div>
                        <div class="stat-column">
                            <div class="stat-label">DIRECTION</div>
                            <div class="stat-value">${getCardinalDirection(parseFloat(game.wind_direction) || 0)}</div>
                        </div>
                    </div>
                    <div class="weather-stats">
                        <div class="stat-column">
                            <div class="stat-label">HR IMPACT</div>
                            <div class="stat-value ${hrImpactClass}">${hrImpactSign}${Math.abs(parseFloat(game.hr_weather_adjustment || 0))}%</div>
                        </div>
                    </div>

                    <!-- Wind Graphic -->
                    <div class="wind-graphic">
                        <div class="wind-label">WINDS <span class="wind-value">${hrImpactSign}${Math.abs(parseFloat(game.hr_weather_adjustment || 0) * 0.4).toFixed(1)}% carry</span></div>
                        <div class="wind-direction">from ${getCardinalDirection(parseFloat(game.wind_direction) || 0)}</div>
                    </div>

                    <!-- Condition -->
                    <div class="condition-row">
                        <span class="condition-dot" style="background: ${parseFloat(game.hr_weather_adjustment || 0) >= 0 ? '#10B981' : '#EF4444'}"></span>
                        <span class="condition-text">${game.weather_main || 'Clear'}</span>
                        <span class="condition-hourly">Hourly (5)</span>
                    </div>

                    <!-- Hourly Forecast -->
                    <div class="hourly-forecast">
                        <div class="hourly-label">BALLPARK LOCAL TIME (ET)</div>
                        <div class="hourly-cards">
                            ${generateHourlyCards()}
                        </div>
                    </div>
                </div>
                <div class="game-actions">
                    <button class="game-btn btn-primary-sm" data-game-id="${game.game_pk}">Detail</button>
                    <button class="game-btn btn-outline-sm">Track</button>
                </div>
            </div>
        `;
    }

    function generateHourlyCards() {
        let html = '';
        const baseTime = new Date();
        baseTime.setHours(12, 0, 0, 0); // Start at noon

        for (let i = 0; i < 5; i++) {
            const hour = baseTime.getHours() + i;
            const displayHour = hour > 12 ? hour - 12 : hour === 0 ? 12 : hour;
            const period = hour >= 12 ? 'PM' : 'AM';

            // Generate realistic hourly data
            const temp = Math.floor(65 + Math.random() * 20); // 65-85°F
            const precip = Math.floor(Math.random() * 30); // 0-30%
            const humidity = Math.floor(40 + Math.random() * 40); // 40-80%
            const windSpeed = Math.floor(0 + Math.random() * 15); // 0-15 mph
            const windDir = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'][Math.floor(Math.random() * 8)];

            html += `
                <div class="hourly-card">
                    <div class="hourly-time">${displayHour}${period}</div>
                    <div class="hourly-icon">${getWeatherIcon()}</div>
                    <div class="hourly-temp">${temp}°</div>
                    <div class="hourly-precip">${precip}%</div>
                    <div class="hourly-humidity">${humidity}%</div>
                    <div class="hourly-wind">${windSpeed} ${windDir}</div>
                </div>
            `;
        }

        return html;
    }

    function getWeatherIcon() {
        const icons = ['☀️', '⛅', '🌤️', '🌥️', '☁️', '🌦️', '🌧️', '⛈️'];
        return icons[Math.floor(Math.random() * icons.length)];
    }

    function formatTime(dateString) {
        if (!dateString) return 'TBD';
        try {
            const date = new Date(dateString);
            return date.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true });
        } catch (e) {
            return 'TBD';
        }
    }

    function getCardinalDirection(degrees) {
        if (isNaN(degrees)) return 'N/A';
        const directions = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"];
        const index = Math.round(degrees / 22.5) % 16;
        return directions[index];
    }

    function setupEventListeners() {
        // Sidebar toggle
        if (sidebarToggle) {
            sidebarToggle.addEventListener('click', () => {
                sidebar.classList.add('open');
                overlay.classList.add('active');
                document.body.style.overflow = 'hidden';
            });
        }

        if (sidebarClose) {
            sidebarClose.addEventListener('click', () => {
                sidebar.classList.remove('open');
                overlay.classList.remove('active');
                document.body.style.overflow = '';
            });
        }

        if (overlay) {
            overlay.addEventListener('click', () => {
                sidebar.classList.remove('open');
                overlay.classList.remove('active');
                document.body.style.overflow = '';
            });
        }

        // Escape key to close sidebar
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && sidebar.classList.contains('open')) {
                sidebar.classList.remove('open');
                overlay.classList.remove('active');
                document.body.style.overflow = '';
            }
        });

        // Filter inputs
        if (dateFilter) {
            dateFilter.addEventListener('change', () => {
                renderGames();
            });
        }

        if (searchFilter) {
            searchFilter.addEventListener('input', () => {
                renderGames();
            });
        }

        // Action buttons
        if (todayBtn) {
            todayBtn.addEventListener('click', () => {
                // In a real app, this would navigate to today's detailed view
                alert('Today\'s games view would show detailed analytics for today\'s matchups');
            });
        }

        if (seasonBtn) {
            seasonBtn.addEventListener('click', () => {
                // In a real app, this would navigate to season trends
                alert('Season trends would show historical performance analytics and trends');
            });
        }

        // Game card clicks (for detail view)
        if (gamesGrid) {
            gamesGrid.addEventListener('click', (e) => {
                const gameBtn = e.target.closest('.game-btn[data-game-id]');
                if (gameBtn) {
                    const gameId = gameBtn.getAttribute('data-game-id');
                    alert(`Game detail view for game ID: ${gameId} would show detailed matchup analytics, weather impact, and betting recommendations`);
                }
            });
        }

        // Responsive handling
        window.addEventListener('resize', () => {
            if (window.innerWidth > 768) {
                sidebar.classList.remove('open');
                overlay.classList.remove('active');
                document.body.style.overflow = '';
            }
        });
    }

    // Render batter leaders
    function renderBatterLeaders() {
        const container = document.getElementById('batterLeadersContainer');
        if (!container) return;

        if (!batterLeadersData || !batterLeadersData.batters || batterLeadersData.batters.length === 0) {
            container.innerHTML = '<p class="no-data">No batter data available</p>';
            return;
        }

        // We'll show the top 5 batters
        const topBatters = batterLeadersData.batters.slice(0, 5);

        // Create a table or a list of cards
        let html = `
            <div class="leaders-table">
                <div class="leaders-header">
                    <div class="leader-rank">Rank</div>
                    <div class="leader-name">Player</div>
                    <div class="leader-barrel">Barrel %</div>
                    <div class="leader-xhr">xHR %</div>
                </div>
                <div class="leaders-body">
        `;

        topBatters.forEach((batter, index) => {
            html += `
                <div class="leader-row">
                    <div class="leader-rank">${index + 1}</div>
                    <div class="leader-name">${batter.player_name}</div>
                    <div class="leader-barrel">${batter.barrel_pct_season.toFixed(2)}%</div>
                    <div class="leader-xhr">${batter.xhr_pct_season.toFixed(2)}%</div>
                </div>
            `;
        });

        html += `
                </div>
            </div>
            <p class="last-updated">Last updated: ${batterLeadersData.last_updated}</p>
        `;

        container.innerHTML = html;
    }

// Initial load
    if (gamesGrid) {
        // Show loading state initially
        gamesGrid.innerHTML = '<div class="loading">Loading games...</div>';
    }
});

// Simple CSS for loading state (would ideally be in style.css)
const style = document.createElement('style');
style.textContent = `
    .loading {
        display: flex;
        justify-content: center;
        align-items: center;
        height: 200px;
        color: #64748B;
        font-style: italy;
    }

    .no-data {
        display: flex;
        justify-content: center;
        align-items: center;
        height: 200px;
        color: #64748B;
    }

    .game-btn {
        transition: all 0.2s ease;
    }

    .game-btn:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
    }

    .positive { color: #10B981; }
    .negative { color: #EF4444; }

    .wind-graphic {
        margin: 1rem 0;
        text-align: center;
        font-size: 0.9rem;
        color: #64748B;
    }

    .wind-value {
        font-weight: 600;
        color: #334155;
    }

    .condition-row {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        margin: 1rem 0;
        font-size: 0.9rem;
        color: #64748B;
    }

    .condition-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        display: inline-block;
    }

    .condition-hourly {
        margin-left: auto;
        color: #3B82F6;
        font-size: 0.875rem;
    }

    .hourly-forecast {
        margin: 1.5rem 0;
    }

    .hourly-label {
        font-weight: 600;
        margin-bottom: 0.5rem;
        display: block;
        color: #334155;
    }

    .hourly-cards {
        display: flex;
        gap: 1rem;
        overflow-x: auto;
        padding: 0.5rem 0;
    }

    .hourly-card {
        background: white;
        border: 1px solid #E2E8F0;
        border-radius: 0.5rem;
        padding: 0.75rem;
        text-align: center;
        min-width: 60px;
    }

    .hourly-time {
        font-size: 0.875rem;
        font-weight: 600;
        color: #64748B;
    }

    .hourly-icon {
        font-size: 1.25rem;
        margin: 0.5rem 0;
    }

    .hourly-temp {
        font-size: 1.25rem;
        font-weight: 700;
        color: #334155;
    }

    .hourly-precip, .hourly-humidity, .hourly-wind {
        font-size: 0.875rem;
        color: #64748B;
        margin: 0.25rem 0;
    }

    /* Batters Leaders Styles */
    .leaders-section {
        margin: 4rem 0;
    }
    .leaders-table {
        width: 100%;
        border-collapse: collapse;
        background: white;
        border-radius: var(--radius-lg);
        overflow: hidden;
        box-shadow: var(--shadow);
    }
    .leaders-header {
        display: grid;
        grid-template-columns: 60px 1fr 150px 150px;
        padding: 1rem;
        background-color: #f8fafc;
        font-weight: 600;
        border-bottom: 1px solid #e2e8f0;
        color: #334155;
    }
    .leaders-body {
        display: grid;
        gap: 0.5rem;
    }
    .leader-row {
        display: grid;
        grid-template-columns: 60px 1fr 150px 150px;
        padding: 1rem;
        border-bottom: 1px solid #f1f5f9;
        align-items: center;
    }
    .leader-row:hover {
        background-color: #f8fafc;
    }
    .leader-row:last-child {
        border-bottom: none;
    }
    .leader-rank {
        font-weight: 700;
        color: #3b82f6;
    }
    .leader-name {
        font-weight: 500;
    }
    .leader-barrel, .leader-xhr {
        font-weight: 600;
        text-align: center;
    }
    .last-updated {
        text-align: center;
        margin-top: 1.5rem;
        color: #64748b;
        font-size: 0.875rem;
    }
`;
document.head.appendChild(style);