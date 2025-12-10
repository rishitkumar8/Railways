# RailWat: Railway AI Simulation Platform

RailWat is an advanced railway simulation platform that combines AI-driven decision making with real-time parameter computation for train operations, track management, and environmental modeling. The system provides a comprehensive framework for simulating railway networks with intelligent parameter optimization.

## Features

### 🚂 Train Parameter Computation
- Real-time calculation of 20+ train-specific parameters (speed, priority, safety metrics)
- Deterministic algorithms for train behavior modeling
- Integration with AI decision systems

### 🛤️ Track Segmentation & Analysis
- 100-meter track segmentation engine
- Dynamic track parameter computation (geometry, infrastructure metrics)
- Environment-aware track modeling

### 🤖 AI Decision Engine
- Extreme AI server for intelligent railway decisions
- Smart AI server for optimized operations
- Environment modeling with station and segment-specific parameters

### 🗺️ Interactive Visualization
- Next.js-based web interface with MapLibre GL maps
- Real-time train positioning and network visualization
- React components for interactive railway management

### 📊 Comprehensive Parameter System
- 140+ parameters covering trains, tracks, stations, and environments
- Collision detection and safety parameters
- Network load and health monitoring
- Environment impact assessment

## Architecture

### Backend (Python)
- `extreme_ai_server.py` - Main AI decision engine
- `smart_ai_server.py` - Optimized AI operations
- `compute140Parameters.py` - Core parameter computation engine
- `computeTrainParameters.py` - Train-specific calculations
- `computeTrackParameters.py` - Track geometry and infrastructure
- `track_segmenter.py` - 100m track segmentation
- `environment_model.py` - Environmental parameter generation

### Frontend (TypeScript/React)
- Next.js 16 with React 19
- MapLibre GL for interactive maps
- Zustand for state management
- Tailwind CSS for styling
- TypeScript for type safety

## Getting Started

### Prerequisites
- Python 3.8+
- Node.js 18+
- npm or yarn

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd railwat
   ```

2. **Install Python dependencies**
   ```bash
   pip install haversine requests flask
   ```

3. **Install Node.js dependencies**
   ```bash
   npm install
   ```

### Running the Application

1. **Start the AI servers**
   ```bash
   python extreme_ai_server.py &
   python smart_ai_server.py &
   ```

2. **Start the frontend**
   ```bash
   npm run dev
   ```

3. **Open your browser**
   Navigate to [http://localhost:3000](http://localhost:3000)

## API Endpoints

### AI Decision Engine
- `POST /decide` - Make intelligent railway decisions
- `POST /compute140` - Compute comprehensive parameters

### Parameter Computation
- Train parameters (p1-p20)
- Track parameters (p21-p40)
- Station parameters (p41-p60)
- Collision parameters (p61-p80)
- Environment parameters (p81-p100)
- Network parameters (p101-p120)
- Health parameters (p121-p140)

## Testing

Run the test suites:
```bash
python test_compute_train_parameters.py
python test_track_params.py
```

## Project Structure

```
railwat/
├── app/                    # Next.js app directory
├── components/             # React components
├── lib/                    # TypeScript utilities
├── public/                 # Static assets
├── *.py                    # Python backend modules
├── test_*.py              # Test files
└── TODO.md                 # Development roadmap
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
