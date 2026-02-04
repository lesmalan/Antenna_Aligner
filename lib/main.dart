import 'package:flutter/material.dart';
import 'dart:math' show sin;
import 'dart:convert';
import 'package:web_socket_channel/web_socket_channel.dart';

void main() {
  runApp(const MyApp());
}

enum AlignmentStep { azimuth, elevation, finalized }

enum AzimuthPhase {
  waitingForConnection,
  sweepInProgress,
  sweepComplete,
  aligned
}

enum ElevationPhase { waitingForStart, sweepInProgress, sweepComplete, aligned }

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Microwave Signal Alignment',
      theme: ThemeData(
        useMaterial3: true,
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF0D47A1),
          brightness: Brightness.light,
        ),
        appBarTheme: const AppBarTheme(centerTitle: true, elevation: 0),
      ),
      home: const AlignmentPage(),
    );
  }
}

class AlignmentPage extends StatefulWidget {
  const AlignmentPage({super.key});

  @override
  State<AlignmentPage> createState() => _AlignmentPageState();
}

class _AlignmentPageState extends State<AlignmentPage> {
  // WebSocket connection for real-time data from Raspberry Pi
  late WebSocketChannel _channel;
  bool _isConnected = false;
  String _connectionStatus = 'Connecting to Raspberry Pi...';

  // Azimuth sweep data collection
  AzimuthPhase _azimuthPhase = AzimuthPhase.waitingForConnection;
  final List<double> _azimuthSweepRSLData =
      []; // Store all RSL readings during azimuth sweep
  double _azimuthMaxSweepRSL = -100.0; // Max RSL found during azimuth sweep
  int _azimuthTurnbucklesInSweep =
      0; // User input: how many turnbuckles in azimuth sweep
  int _azimuthTurnsToMaxRSL =
      0; // Calculated: how many turns left to reach max RSL
  bool _waitingForAzimuthReading =
      false; // Flag: waiting for next reading to be captured

  // Elevation sweep data collection
  ElevationPhase _elevationPhase = ElevationPhase.waitingForStart;
  final List<double> _elevationSweepRSLData =
      []; // Store all RSL readings during elevation sweep
  double _elevationMaxSweepRSL = -100.0; // Max RSL found during elevation sweep
  int _elevationTurnbucklesInSweep =
      0; // User input: how many turnbuckles in elevation sweep
  int _elevationTurnsFromTopToMax =
      0; // Calculated: how many turns down from top to reach max RSL
  bool _waitingForElevationReading =
      false; // Flag: waiting for next reading to be captured

  // Signal data from Raspberry Pi
  double _currentRSL = -85.5; // dBm
  final double _maxRSL = -75.0; // dBm
  int _azimuthTurnsLeft = 3;
  int _azimuthTurnsRight = 0;
  int _elevationTurnsLeft = 2;
  int _elevationTurnsRight = 0;

  AlignmentStep _currentStep = AlignmentStep.azimuth;
  bool _azimuthConfirmed = false;
  bool _elevationConfirmed = false;
  final int _currentSide = 1; // Track which side we're aligning (1 or 2)
  bool _processCompleted = false; // true when the entire process is finalized

  @override
  void initState() {
    super.initState();
    _connectWebSocket();
  }

  void _connectWebSocket() {
    try {
      _channel = WebSocketChannel.connect(
        Uri.parse('ws://192.168.8.1:8000/ws'),
      );

      _channel.stream.listen(
        (message) {
          if (!mounted) return;
          try {
            final data = jsonDecode(message);
            setState(() {
              _isConnected = true;
              _connectionStatus = 'Connected';

              // Start sweep automatically on first connection
              if (_azimuthPhase == AzimuthPhase.waitingForConnection) {
                _azimuthPhase = AzimuthPhase.sweepInProgress;
                _azimuthSweepRSLData.clear();
                _azimuthMaxSweepRSL = -100.0;
              }

              _currentRSL = (data['rsl'] as num).toDouble();

              // If waiting for azimuth reading during sweep, capture it
              if (_waitingForAzimuthReading &&
                  _azimuthPhase == AzimuthPhase.sweepInProgress) {
                _azimuthSweepRSLData.add(_currentRSL);
                if (_currentRSL > _azimuthMaxSweepRSL) {
                  _azimuthMaxSweepRSL = _currentRSL;
                }
                _waitingForAzimuthReading = false;
              }

              // If waiting for elevation reading during sweep, capture it
              if (_waitingForElevationReading &&
                  _elevationPhase == ElevationPhase.sweepInProgress) {
                _elevationSweepRSLData.add(_currentRSL);
                if (_currentRSL > _elevationMaxSweepRSL) {
                  _elevationMaxSweepRSL = _currentRSL;
                }
                _waitingForElevationReading = false;
              }

              // Optionally update turns if provided by server
              if (data.containsKey('azimuth_turns_left')) {
                _azimuthTurnsLeft = data['azimuth_turns_left'] as int;
              }
              if (data.containsKey('azimuth_turns_right')) {
                _azimuthTurnsRight = data['azimuth_turns_right'] as int;
              }
              if (data.containsKey('elevation_turns_left')) {
                _elevationTurnsLeft = data['elevation_turns_left'] as int;
              }
              if (data.containsKey('elevation_turns_right')) {
                _elevationTurnsRight = data['elevation_turns_right'] as int;
              }
            });
          } catch (e) {
            debugPrint('Error parsing WebSocket data: $e');
          }
        },
        onError: (error) {
          if (mounted) {
            setState(() {
              _isConnected = false;
              _connectionStatus = 'Connection error: $error';
            });
          }
          debugPrint('WebSocket error: $error');
        },
        onDone: () {
          if (mounted) {
            setState(() {
              _isConnected = false;
              _connectionStatus = 'Connection closed';
            });
          }
          // Attempt to reconnect after 3 seconds
          Future.delayed(const Duration(seconds: 3), _connectWebSocket);
        },
      );
    } catch (e) {
      if (mounted) {
        setState(() {
          _isConnected = false;
          _connectionStatus = 'Failed to connect: $e';
        });
      }
      debugPrint('WebSocket connection error: $e');
      // Attempt to reconnect after 3 seconds
      Future.delayed(const Duration(seconds: 3), _connectWebSocket);
    }
  }

  @override
  void dispose() {
    _channel.sink.close();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    // Show connection screen if not yet connected
    if (!_isConnected) {
      return Scaffold(
        body: Container(
          decoration: BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: [
                Theme.of(context).colorScheme.primary,
                Colors.blue[900]!,
              ],
            ),
          ),
          child: Center(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const SizedBox(height: 40),
                const CircularProgressIndicator(
                  valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
                  strokeWidth: 3,
                ),
                const SizedBox(height: 32),
                Text(
                  'Connecting to Raspberry Pi',
                  style: Theme.of(context).textTheme.titleLarge?.copyWith(
                        color: Colors.white,
                        fontWeight: FontWeight.bold,
                      ),
                ),
                const SizedBox(height: 12),
                Text(
                  'IP: 192.168.8.1:8000',
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                        color: Colors.white70,
                      ),
                ),
                const SizedBox(height: 16),
                Text(
                  _connectionStatus,
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: Colors.white60,
                        fontStyle: FontStyle.italic,
                      ),
                  textAlign: TextAlign.center,
                ),
              ],
            ),
          ),
        ),
      );
    }

    // Show sweep phase screen
    if (_azimuthPhase == AzimuthPhase.sweepInProgress ||
        _azimuthPhase == AzimuthPhase.sweepComplete) {
      return _buildAzimuthSweepScreen();
    }

    // Show elevation sweep phase screen
    if (_elevationPhase == ElevationPhase.sweepInProgress ||
        _elevationPhase == ElevationPhase.sweepComplete) {
      return _buildElevationSweepScreen();
    }

    // Show alignment screen (original flow)
    if (_processCompleted) {
      return Scaffold(
        body: Container(
          decoration: BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: [
                Theme.of(context).colorScheme.primary,
                Colors.green[700]!,
              ],
            ),
          ),
          child: Center(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const Icon(Icons.check_circle, size: 120, color: Colors.white),
                const SizedBox(height: 32),
                Text(
                  'System aligned. Please disconnect device from antenna.',
                  style: Theme.of(context).textTheme.titleLarge?.copyWith(
                        color: Colors.white,
                        fontWeight: FontWeight.bold,
                      ),
                  textAlign: TextAlign.center,
                ),
              ],
            ),
          ),
        ),
      );
    }

    return Scaffold(
      appBar: AppBar(
        title: Text('Microwave Signal Alignment - Side $_currentSide'),
        backgroundColor: Theme.of(context).colorScheme.primary,
        foregroundColor: Colors.white,
        actions: [
          // Connection status indicator
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: Center(
              child: Tooltip(
                message: _connectionStatus,
                child: Row(
                  children: [
                    Icon(
                      _isConnected ? Icons.cloud_done : Icons.cloud_off,
                      color: _isConnected ? Colors.green[300] : Colors.red[300],
                      size: 20,
                    ),
                    const SizedBox(width: 4),
                    Text(
                      _isConnected ? 'Connected' : 'Offline',
                      style: const TextStyle(fontSize: 12),
                    ),
                  ],
                ),
              ),
            ),
          ),
          IconButton(
            tooltip: 'Support Helpline',
            icon: const Icon(Icons.phone_in_talk),
            onPressed: _showSupportPrompt,
          ),
        ],
      ),
      body: SafeArea(
        child: Column(
          children: [
            // Signal Graph Section
            Expanded(flex: 2, child: _buildSignalGraphSection()),

            // Divider
            const Padding(
              padding: EdgeInsets.symmetric(horizontal: 16),
              child: Divider(thickness: 2),
            ),

            // Alignment Information Section
            Expanded(flex: 1, child: _buildAlignmentInfoSection()),

            // Control Buttons Section
            Expanded(flex: 1, child: _buildControlButtonsSection()),
          ],
        ),
      ),
    );
  }

  Widget _buildAzimuthSweepScreen() {
    if (_azimuthPhase == AzimuthPhase.sweepInProgress) {
      return Scaffold(
        appBar: AppBar(
          title: const Text('Azimuth Sweep'),
          backgroundColor: Theme.of(context).colorScheme.primary,
          foregroundColor: Colors.white,
        ),
        body: SafeArea(
          child: Column(
            children: [
              // Instructions
              Expanded(
                flex: 1,
                child: Container(
                  padding: const EdgeInsets.all(16),
                  color: Colors.blue[50],
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      const Icon(Icons.info, size: 48, color: Colors.blue),
                      const SizedBox(height: 16),
                      Text(
                        'Azimuth Sweep in Progress',
                        style: Theme.of(context).textTheme.titleLarge?.copyWith(
                              fontWeight: FontWeight.bold,
                              color: Colors.black87,
                            ),
                      ),
                      const SizedBox(height: 12),
                      Text(
                        'Rotate the antenna from left to right. The app is collecting signal strength data.',
                        style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                              color: Colors.black54,
                            ),
                        textAlign: TextAlign.center,
                      ),
                    ],
                  ),
                ),
              ),
              // Real-time signal graph
              Expanded(
                flex: 2,
                child: _buildSignalGraphSection(),
              ),
              // Sweep data info
              Expanded(
                flex: 1,
                child: Container(
                  padding: const EdgeInsets.all(16),
                  color: Colors.grey[100],
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                        children: [
                          Column(
                            children: [
                              Text(
                                'Data Points',
                                style: Theme.of(context)
                                    .textTheme
                                    .labelSmall
                                    ?.copyWith(color: Colors.grey[600]),
                              ),
                              const SizedBox(height: 4),
                              Text(
                                '${_azimuthSweepRSLData.length}',
                                style: Theme.of(context)
                                    .textTheme
                                    .headlineSmall
                                    ?.copyWith(fontWeight: FontWeight.bold),
                              ),
                            ],
                          ),
                          Column(
                            children: [
                              Text(
                                'Max RSL Found',
                                style: Theme.of(context)
                                    .textTheme
                                    .labelSmall
                                    ?.copyWith(color: Colors.grey[600]),
                              ),
                              const SizedBox(height: 4),
                              Text(
                                '${_azimuthMaxSweepRSL.toStringAsFixed(1)} dBm',
                                style: Theme.of(context)
                                    .textTheme
                                    .headlineSmall
                                    ?.copyWith(
                                      fontWeight: FontWeight.bold,
                                      color: Colors.green[700],
                                    ),
                              ),
                            ],
                          ),
                          Column(
                            children: [
                              Text(
                                'Current RSL',
                                style: Theme.of(context)
                                    .textTheme
                                    .labelSmall
                                    ?.copyWith(color: Colors.grey[600]),
                              ),
                              const SizedBox(height: 4),
                              Text(
                                '${_currentRSL.toStringAsFixed(1)} dBm',
                                style: Theme.of(context)
                                    .textTheme
                                    .headlineSmall
                                    ?.copyWith(fontWeight: FontWeight.bold),
                              ),
                            ],
                          ),
                        ],
                      ),
                      const SizedBox(height: 24),
                      SizedBox(
                        width: double.infinity,
                        child: Column(
                          children: [
                            ElevatedButton.icon(
                              onPressed: _takeAzimuthReading,
                              icon: const Icon(Icons.camera_alt),
                              label: const Text('Take Reading'),
                              style: ElevatedButton.styleFrom(
                                backgroundColor:
                                    Theme.of(context).colorScheme.primary,
                                foregroundColor: Colors.white,
                                padding: const EdgeInsets.symmetric(
                                  horizontal: 32,
                                  vertical: 16,
                                ),
                              ),
                            ),
                            const SizedBox(height: 12),
                            ElevatedButton.icon(
                              onPressed: _completeSweep,
                              icon: const Icon(Icons.check),
                              label: const Text('Sweep Complete'),
                              style: ElevatedButton.styleFrom(
                                backgroundColor: Colors.green[600],
                                foregroundColor: Colors.white,
                                padding: const EdgeInsets.symmetric(
                                  horizontal: 32,
                                  vertical: 16,
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      );
    }

    // Sweep complete - ask for number of turnbuckles
    if (_azimuthPhase == AzimuthPhase.sweepComplete) {
      return Scaffold(
        appBar: AppBar(
          title: const Text('Azimuth Alignment'),
          backgroundColor: Theme.of(context).colorScheme.primary,
          foregroundColor: Colors.white,
        ),
        body: SafeArea(
          child: Column(
            children: [
              Expanded(
                child: SingleChildScrollView(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      // Sweep results
                      Container(
                        padding: const EdgeInsets.all(16),
                        decoration: BoxDecoration(
                          color: Colors.green[50],
                          border: Border.all(color: Colors.green[300]!),
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              children: [
                                const Icon(Icons.check_circle,
                                    color: Colors.green, size: 24),
                                const SizedBox(width: 8),
                                Text(
                                  'Sweep Complete',
                                  style: Theme.of(context)
                                      .textTheme
                                      .titleMedium
                                      ?.copyWith(
                                        fontWeight: FontWeight.bold,
                                        color: Colors.green[700],
                                      ),
                                ),
                              ],
                            ),
                            const SizedBox(height: 16),
                            Text(
                              'Sweep Results:',
                              style: Theme.of(context)
                                  .textTheme
                                  .titleSmall
                                  ?.copyWith(fontWeight: FontWeight.bold),
                            ),
                            const SizedBox(height: 8),
                            Text(
                              'Data points collected: ${_azimuthSweepRSLData.length}',
                              style: Theme.of(context).textTheme.bodyMedium,
                            ),
                            const SizedBox(height: 4),
                            Text(
                              'Maximum RSL found: ${_azimuthMaxSweepRSL.toStringAsFixed(1)} dBm',
                              style: Theme.of(context)
                                  .textTheme
                                  .bodyMedium
                                  ?.copyWith(
                                    color: Colors.green[700],
                                    fontWeight: FontWeight.bold,
                                  ),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(height: 32),
                      // Input section
                      Text(
                        'How many turnbuckles were in your sweep?',
                        style: Theme.of(context)
                            .textTheme
                            .titleMedium
                            ?.copyWith(fontWeight: FontWeight.bold),
                      ),
                      const SizedBox(height: 16),
                      TextField(
                        keyboardType: TextInputType.number,
                        onChanged: (value) {
                          setState(() {
                            _azimuthTurnbucklesInSweep =
                                int.tryParse(value) ?? 0;
                          });
                        },
                        decoration: InputDecoration(
                          hintText: 'Enter number of turnbuckles',
                          border: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(8),
                          ),
                          prefixIcon: const Icon(Icons.settings),
                          contentPadding: const EdgeInsets.symmetric(
                            horizontal: 16,
                            vertical: 12,
                          ),
                        ),
                      ),
                      const SizedBox(height: 24),
                      if (_azimuthTurnbucklesInSweep > 0) ...[
                        Container(
                          padding: const EdgeInsets.all(16),
                          decoration: BoxDecoration(
                            color: Colors.blue[50],
                            border: Border.all(color: Colors.blue[300]!),
                            borderRadius: BorderRadius.circular(12),
                          ),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                'Alignment Instructions:',
                                style: Theme.of(context)
                                    .textTheme
                                    .titleSmall
                                    ?.copyWith(fontWeight: FontWeight.bold),
                              ),
                              const SizedBox(height: 12),
                              Text(
                                'You rotated through $_azimuthTurnbucklesInSweep turnbuckles',
                                style: Theme.of(context).textTheme.bodyMedium,
                              ),
                              const SizedBox(height: 8),
                              Text(
                                'Maximum signal was at: ${_azimuthMaxSweepRSL.toStringAsFixed(1)} dBm',
                                style: Theme.of(context)
                                    .textTheme
                                    .bodyMedium
                                    ?.copyWith(
                                      color: Colors.green[700],
                                      fontWeight: FontWeight.bold,
                                    ),
                              ),
                              const SizedBox(height: 12),
                              Container(
                                padding: const EdgeInsets.all(12),
                                decoration: BoxDecoration(
                                  color: Colors.orange[50],
                                  border:
                                      Border.all(color: Colors.orange[300]!),
                                  borderRadius: BorderRadius.circular(8),
                                ),
                                child: RichText(
                                  text: TextSpan(
                                    style:
                                        Theme.of(context).textTheme.bodyMedium,
                                    children: [
                                      const TextSpan(
                                        text:
                                            'You are currently at the RIGHT end of your sweep. You need to turn LEFT ',
                                      ),
                                      TextSpan(
                                        text:
                                            '$_azimuthTurnbucklesInSweep turnbuckles',
                                        style: const TextStyle(
                                          fontWeight: FontWeight.bold,
                                          color: Colors.orange,
                                        ),
                                      ),
                                      const TextSpan(
                                        text: ' to reach the maximum signal.',
                                      ),
                                    ],
                                  ),
                                ),
                              ),
                            ],
                          ),
                        ),
                        const SizedBox(height: 24),
                        SizedBox(
                          width: double.infinity,
                          child: ElevatedButton.icon(
                            onPressed: _confirmAzimuthAlignment,
                            icon: const Icon(Icons.done),
                            label: const Text('Confirm Alignment'),
                            style: ElevatedButton.styleFrom(
                              backgroundColor:
                                  Theme.of(context).colorScheme.primary,
                              foregroundColor: Colors.white,
                              padding: const EdgeInsets.symmetric(
                                horizontal: 32,
                                vertical: 16,
                              ),
                            ),
                          ),
                        ),
                      ],
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      );
    }

    return const SizedBox.shrink();
  }

  Widget _buildElevationSweepScreen() {
    if (_elevationPhase == ElevationPhase.sweepInProgress) {
      return Scaffold(
        appBar: AppBar(
          title: const Text('Elevation Sweep'),
          backgroundColor: Theme.of(context).colorScheme.primary,
          foregroundColor: Colors.white,
        ),
        body: SafeArea(
          child: Column(
            children: [
              // Instructions
              Expanded(
                flex: 1,
                child: Container(
                  padding: const EdgeInsets.all(16),
                  color: Colors.blue[50],
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      const Icon(Icons.info, size: 48, color: Colors.blue),
                      const SizedBox(height: 16),
                      Text(
                        'Elevation Sweep in Progress',
                        style: Theme.of(context).textTheme.titleLarge?.copyWith(
                              fontWeight: FontWeight.bold,
                              color: Colors.black87,
                            ),
                      ),
                      const SizedBox(height: 12),
                      Text(
                        'Rotate the antenna from bottom to top. Click "Take Reading" at each position.',
                        style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                              color: Colors.black54,
                            ),
                        textAlign: TextAlign.center,
                      ),
                    ],
                  ),
                ),
              ),
              // Real-time signal graph
              Expanded(
                flex: 2,
                child: _buildSignalGraphSection(),
              ),
              // Sweep data info
              Expanded(
                flex: 1,
                child: Container(
                  padding: const EdgeInsets.all(16),
                  color: Colors.grey[100],
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                        children: [
                          Column(
                            children: [
                              Text(
                                'Data Points',
                                style: Theme.of(context)
                                    .textTheme
                                    .labelSmall
                                    ?.copyWith(color: Colors.grey[600]),
                              ),
                              const SizedBox(height: 4),
                              Text(
                                '${_elevationSweepRSLData.length}',
                                style: Theme.of(context)
                                    .textTheme
                                    .headlineSmall
                                    ?.copyWith(fontWeight: FontWeight.bold),
                              ),
                            ],
                          ),
                          Column(
                            children: [
                              Text(
                                'Max RSL Found',
                                style: Theme.of(context)
                                    .textTheme
                                    .labelSmall
                                    ?.copyWith(color: Colors.grey[600]),
                              ),
                              const SizedBox(height: 4),
                              Text(
                                '${_elevationMaxSweepRSL.toStringAsFixed(1)} dBm',
                                style: Theme.of(context)
                                    .textTheme
                                    .headlineSmall
                                    ?.copyWith(
                                      fontWeight: FontWeight.bold,
                                      color: Colors.green[700],
                                    ),
                              ),
                            ],
                          ),
                          Column(
                            children: [
                              Text(
                                'Current RSL',
                                style: Theme.of(context)
                                    .textTheme
                                    .labelSmall
                                    ?.copyWith(color: Colors.grey[600]),
                              ),
                              const SizedBox(height: 4),
                              Text(
                                '${_currentRSL.toStringAsFixed(1)} dBm',
                                style: Theme.of(context)
                                    .textTheme
                                    .headlineSmall
                                    ?.copyWith(fontWeight: FontWeight.bold),
                              ),
                            ],
                          ),
                        ],
                      ),
                      const SizedBox(height: 24),
                      SizedBox(
                        width: double.infinity,
                        child: Column(
                          children: [
                            ElevatedButton.icon(
                              onPressed: _takeElevationReading,
                              icon: const Icon(Icons.camera_alt),
                              label: const Text('Take Reading'),
                              style: ElevatedButton.styleFrom(
                                backgroundColor:
                                    Theme.of(context).colorScheme.primary,
                                foregroundColor: Colors.white,
                                padding: const EdgeInsets.symmetric(
                                  horizontal: 32,
                                  vertical: 16,
                                ),
                              ),
                            ),
                            const SizedBox(height: 12),
                            ElevatedButton.icon(
                              onPressed: _completeElevationSweep,
                              icon: const Icon(Icons.check),
                              label: const Text('Sweep Complete'),
                              style: ElevatedButton.styleFrom(
                                backgroundColor: Colors.green[600],
                                foregroundColor: Colors.white,
                                padding: const EdgeInsets.symmetric(
                                  horizontal: 32,
                                  vertical: 16,
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      );
    }

    // Elevation sweep complete - ask for number of turnbuckles
    if (_elevationPhase == ElevationPhase.sweepComplete) {
      return Scaffold(
        appBar: AppBar(
          title: const Text('Elevation Alignment'),
          backgroundColor: Theme.of(context).colorScheme.primary,
          foregroundColor: Colors.white,
        ),
        body: SafeArea(
          child: Column(
            children: [
              Expanded(
                child: SingleChildScrollView(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      // Sweep results
                      Container(
                        padding: const EdgeInsets.all(16),
                        decoration: BoxDecoration(
                          color: Colors.green[50],
                          border: Border.all(color: Colors.green[300]!),
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              children: [
                                const Icon(Icons.check_circle,
                                    color: Colors.green, size: 24),
                                const SizedBox(width: 8),
                                Text(
                                  'Sweep Complete',
                                  style: Theme.of(context)
                                      .textTheme
                                      .titleMedium
                                      ?.copyWith(
                                        fontWeight: FontWeight.bold,
                                        color: Colors.green[700],
                                      ),
                                ),
                              ],
                            ),
                            const SizedBox(height: 16),
                            Text(
                              'Sweep Results:',
                              style: Theme.of(context)
                                  .textTheme
                                  .titleSmall
                                  ?.copyWith(fontWeight: FontWeight.bold),
                            ),
                            const SizedBox(height: 8),
                            Text(
                              'Data points collected: ${_elevationSweepRSLData.length}',
                              style: Theme.of(context).textTheme.bodyMedium,
                            ),
                            const SizedBox(height: 4),
                            Text(
                              'Maximum RSL found: ${_elevationMaxSweepRSL.toStringAsFixed(1)} dBm',
                              style: Theme.of(context)
                                  .textTheme
                                  .bodyMedium
                                  ?.copyWith(
                                    color: Colors.green[700],
                                    fontWeight: FontWeight.bold,
                                  ),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(height: 32),
                      // Input section
                      Text(
                        'How many turnbuckles were in your sweep?',
                        style: Theme.of(context)
                            .textTheme
                            .titleMedium
                            ?.copyWith(fontWeight: FontWeight.bold),
                      ),
                      const SizedBox(height: 16),
                      TextField(
                        keyboardType: TextInputType.number,
                        onChanged: (value) {
                          setState(() {
                            _elevationTurnbucklesInSweep =
                                int.tryParse(value) ?? 0;
                          });
                        },
                        decoration: InputDecoration(
                          hintText: 'Enter number of turnbuckles',
                          border: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(8),
                          ),
                          prefixIcon: const Icon(Icons.settings),
                          contentPadding: const EdgeInsets.symmetric(
                            horizontal: 16,
                            vertical: 12,
                          ),
                        ),
                      ),
                      const SizedBox(height: 24),
                      if (_elevationTurnbucklesInSweep > 0) ...[
                        Container(
                          padding: const EdgeInsets.all(16),
                          decoration: BoxDecoration(
                            color: Colors.blue[50],
                            border: Border.all(color: Colors.blue[300]!),
                            borderRadius: BorderRadius.circular(12),
                          ),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                'Alignment Instructions:',
                                style: Theme.of(context)
                                    .textTheme
                                    .titleSmall
                                    ?.copyWith(fontWeight: FontWeight.bold),
                              ),
                              const SizedBox(height: 12),
                              Text(
                                'You rotated through $_elevationTurnbucklesInSweep turnbuckles',
                                style: Theme.of(context).textTheme.bodyMedium,
                              ),
                              const SizedBox(height: 8),
                              Text(
                                'Maximum signal was at: ${_elevationMaxSweepRSL.toStringAsFixed(1)} dBm',
                                style: Theme.of(context)
                                    .textTheme
                                    .bodyMedium
                                    ?.copyWith(
                                      color: Colors.green[700],
                                      fontWeight: FontWeight.bold,
                                    ),
                              ),
                              const SizedBox(height: 12),
                              Container(
                                padding: const EdgeInsets.all(12),
                                decoration: BoxDecoration(
                                  color: Colors.orange[50],
                                  border:
                                      Border.all(color: Colors.orange[300]!),
                                  borderRadius: BorderRadius.circular(8),
                                ),
                                child: RichText(
                                  text: TextSpan(
                                    style:
                                        Theme.of(context).textTheme.bodyMedium,
                                    children: [
                                      const TextSpan(
                                        text:
                                            'You are currently at the TOP of your sweep. You need to go DOWN ',
                                      ),
                                      TextSpan(
                                        text:
                                            '$_elevationTurnsFromTopToMax turnbuckles',
                                        style: const TextStyle(
                                          fontWeight: FontWeight.bold,
                                          color: Colors.orange,
                                        ),
                                      ),
                                      const TextSpan(
                                        text: ' to reach the maximum signal.',
                                      ),
                                    ],
                                  ),
                                ),
                              ),
                            ],
                          ),
                        ),
                        const SizedBox(height: 24),
                        SizedBox(
                          width: double.infinity,
                          child: ElevatedButton.icon(
                            onPressed: _confirmElevationAlignment,
                            icon: const Icon(Icons.done),
                            label: const Text('Confirm Alignment'),
                            style: ElevatedButton.styleFrom(
                              backgroundColor:
                                  Theme.of(context).colorScheme.primary,
                              foregroundColor: Colors.white,
                              padding: const EdgeInsets.symmetric(
                                horizontal: 32,
                                vertical: 16,
                              ),
                            ),
                          ),
                        ),
                      ],
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      );
    }

    return const SizedBox.shrink();
  }

  Widget _buildSignalGraphSection() {
    return Container(
      padding: const EdgeInsets.all(16),
      color: Colors.grey[50],
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Title
          Text(
            'Signal Strength (RSL)',
            style: Theme.of(context).textTheme.titleLarge?.copyWith(
                  fontWeight: FontWeight.bold,
                  color: Colors.black87,
                ),
          ),
          const SizedBox(height: 8),

          // Current RSL Value
          Row(
            children: [
              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 12,
                  vertical: 6,
                ),
                decoration: BoxDecoration(
                  color: Theme.of(context).colorScheme.primary,
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(
                  'Current: $_currentRSL dBm',
                  style: const TextStyle(
                    color: Colors.white,
                    fontWeight: FontWeight.bold,
                    fontSize: 14,
                  ),
                ),
              ),
              const SizedBox(width: 16),
              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 12,
                  vertical: 6,
                ),
                decoration: BoxDecoration(
                  color: Colors.green[600],
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(
                  'Max: $_maxRSL dBm',
                  style: const TextStyle(
                    color: Colors.white,
                    fontWeight: FontWeight.bold,
                    fontSize: 14,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),

          // TODO: Implement actual signal graph using a charting library (e.g., fl_chart)
          // This should display a real-time graph of signal strength over time
          // For now, showing a sine wave graph representation
          Expanded(
            child: Container(
              decoration: BoxDecoration(
                color: Colors.white,
                border: Border.all(color: Colors.grey[300]!),
                borderRadius: BorderRadius.circular(12),
              ),
              padding: const EdgeInsets.all(12),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                crossAxisAlignment: CrossAxisAlignment.center,
                children: [
                  // Sine wave signal visualization
                  Expanded(
                    child: CustomPaint(
                      painter: SineWavePainter(
                        currentRSL: _currentRSL,
                        maxRSL: _maxRSL,
                      ),
                      size: Size.infinite,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    'Real-time Signal Graph',
                    style: Theme.of(
                      context,
                    ).textTheme.bodySmall?.copyWith(color: Colors.grey[600]),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildAlignmentInfoSection() {
    return Container(
      padding: const EdgeInsets.all(16),
      child: SingleChildScrollView(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Current Step Indicator
            Text(
              _currentStep == AlignmentStep.azimuth
                  ? 'Step 1: Azimuth Alignment'
                  : _currentStep == AlignmentStep.elevation
                      ? 'Step 2: Elevation Alignment'
                      : 'All Alignments Complete',
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.bold,
                    color: Theme.of(context).colorScheme.primary,
                  ),
            ),
            const SizedBox(height: 12),

            // Azimuth Information
            _buildAlignmentCard(
              title: 'Azimuth',
              turnsLeft: _azimuthTurnsLeft,
              turnsRight: _azimuthTurnsRight,
              isActive: _currentStep == AlignmentStep.azimuth,
              isConfirmed: _azimuthConfirmed,
            ),
            const SizedBox(height: 8),

            // Elevation Information
            _buildAlignmentCard(
              title: 'Elevation',
              turnsLeft: _elevationTurnsLeft,
              turnsRight: _elevationTurnsRight,
              isActive: _currentStep == AlignmentStep.elevation,
              isConfirmed: _elevationConfirmed,
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildAlignmentCard({
    required String title,
    required int turnsLeft,
    required int turnsRight,
    required bool isActive,
    required bool isConfirmed,
  }) {
    return Container(
      decoration: BoxDecoration(
        color: isActive ? Colors.blue[50] : Colors.white,
        border: Border.all(
          color: isConfirmed
              ? Colors.green[600]!
              : isActive
                  ? Theme.of(context).colorScheme.primary
                  : Colors.grey[300]!,
          width: 2,
        ),
        borderRadius: BorderRadius.circular(10),
      ),
      padding: const EdgeInsets.all(12),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                title,
                style: Theme.of(context).textTheme.titleSmall?.copyWith(
                      fontWeight: FontWeight.bold,
                      color: Colors.black87,
                    ),
              ),
              const SizedBox(height: 4),
              RichText(
                text: TextSpan(
                  style: Theme.of(context).textTheme.bodySmall,
                  children: [
                    if (turnsLeft > 0)
                      TextSpan(
                        text: 'Turn LEFT $turnsLeft',
                        style: const TextStyle(
                          color: Colors.orange,
                          fontWeight: FontWeight.bold,
                        ),
                      )
                    else if (turnsRight > 0)
                      TextSpan(
                        text: 'Turn RIGHT $turnsRight',
                        style: const TextStyle(
                          color: Colors.orange,
                          fontWeight: FontWeight.bold,
                        ),
                      )
                    else
                      const TextSpan(
                        text: 'Aligned ✓',
                        style: TextStyle(
                          color: Colors.green,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                  ],
                ),
              ),
            ],
          ),
          if (isConfirmed)
            Icon(Icons.check_circle, color: Colors.green[600], size: 32),
        ],
      ),
    );
  }

  Widget _buildControlButtonsSection() {
    return Container(
      padding: const EdgeInsets.all(16),
      child: SingleChildScrollView(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.spaceEvenly,
          children: [
            // Show button to start elevation sweep after azimuth is confirmed
            if (_azimuthConfirmed &&
                !_elevationConfirmed &&
                _elevationPhase == ElevationPhase.waitingForStart)
              ElevatedButton.icon(
                onPressed: _startElevationSweep,
                icon: const Icon(Icons.arrow_forward),
                label: const Text('Start Elevation Sweep'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.blue[700],
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(
                    horizontal: 32,
                    vertical: 16,
                  ),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(10),
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }

  void _startElevationSweep() {
    setState(() {
      _elevationPhase = ElevationPhase.sweepInProgress;
      _elevationSweepRSLData.clear();
      _elevationMaxSweepRSL = -100.0;
    });
  }

  void _completeSweep() {
    setState(() {
      _azimuthPhase = AzimuthPhase.sweepComplete;
    });
  }

  void _takeAzimuthReading() {
    setState(() {
      _waitingForAzimuthReading = true;
    });
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('Waiting for reading from Raspberry Pi...'),
        duration: Duration(seconds: 3),
      ),
    );
  }

  void _takeElevationReading() {
    setState(() {
      _waitingForElevationReading = true;
    });
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('Waiting for reading from Raspberry Pi...'),
        duration: Duration(seconds: 3),
      ),
    );
  }

  void _confirmAzimuthAlignment() {
    // Calculate how many turns from right to max
    if (_azimuthTurnbucklesInSweep > 0 && _azimuthSweepRSLData.isNotEmpty) {
      // Find the index of max RSL in the sweep data
      int maxIndex = _azimuthSweepRSLData.indexOf(_azimuthMaxSweepRSL);

      // Calculate how many turnbuckles from the start (left) to the max
      // The technician starts from the left and sweeps right
      // So turnbuckles from left = max index position relative to total sweep
      if (maxIndex >= 0) {
        _azimuthTurnsToMaxRSL = (maxIndex /
                _azimuthSweepRSLData.length *
                _azimuthTurnbucklesInSweep)
            .round();
      }

      setState(() {
        _azimuthPhase = AzimuthPhase.aligned;
        _azimuthConfirmed = true;
        _currentStep = AlignmentStep.elevation;
      });

      _showConfirmationDialog(
        title: 'Azimuth Aligned',
        message:
            'Azimuth alignment complete. You are now at $_azimuthTurnsToMaxRSL turnbuckles from the starting position.\n\nProceeding to elevation alignment...',
        onConfirm: () {
          Navigator.pop(context);
        },
      );
    }
  }

  void _completeElevationSweep() {
    setState(() {
      _elevationPhase = ElevationPhase.sweepComplete;
    });
  }

  void _confirmElevationAlignment() {
    // Calculate how many turns from top to max
    if (_elevationTurnbucklesInSweep > 0 && _elevationSweepRSLData.isNotEmpty) {
      // Find the index of max RSL in the sweep data
      int maxIndex = _elevationSweepRSLData.indexOf(_elevationMaxSweepRSL);

      // Calculate how many turnbuckles down from the top to the max
      // The technician starts at the bottom and sweeps to the top
      // So turns down from top = (total - max index position)
      if (maxIndex >= 0) {
        _elevationTurnsFromTopToMax =
            (_elevationSweepRSLData.length - maxIndex - 1);
      }

      setState(() {
        _elevationPhase = ElevationPhase.aligned;
        _elevationConfirmed = true;
        _processCompleted = true;
      });

      _showConfirmationDialog(
        title: 'Elevation Aligned',
        message:
            'Elevation alignment complete. From the TOP, go DOWN $_elevationTurnsFromTopToMax turnbuckles to reach maximum signal.\n\nAll alignments complete!',
        onConfirm: () {
          Navigator.pop(context);
        },
      );
    }
  }

  void _showConfirmationDialog({
    required String title,
    required String message,
    required VoidCallback onConfirm,
  }) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: Text(title),
        content: Text(message),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: onConfirm,
            style: ElevatedButton.styleFrom(backgroundColor: Colors.green[600]),
            child: const Text('Confirm'),
          ),
        ],
      ),
    );
  }

  // Support helpline prompt: displays the support phone number to call
  void _showSupportPrompt() {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
        title: const Text('Support Helpline'),
        content: const Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Contact our support team at:',
              style: TextStyle(fontSize: 16),
            ),
            SizedBox(height: 16),
            Text(
              '+1-800-555-1234',
              style: TextStyle(
                fontSize: 20,
                fontWeight: FontWeight.bold,
                color: Color(0xFF0D47A1),
              ),
            ),
          ],
        ),
        actions: [
          ElevatedButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Close'),
          ),
        ],
      ),
    );
  }
}

class SineWavePainter extends CustomPainter {
  final double currentRSL;
  final double maxRSL;

  SineWavePainter({required this.currentRSL, required this.maxRSL});

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = const Color(0xFF0D47A1)
      ..strokeWidth = 3
      ..strokeCap = StrokeCap.round
      ..strokeJoin = StrokeJoin.round
      ..style = PaintingStyle.stroke;

    final fillPaint = Paint()
      ..color = const Color(0xFF0D47A1).withValues(alpha: 0.1)
      ..style = PaintingStyle.fill;

    final gridPaint = Paint()
      ..color = Colors.grey[300]!
      ..strokeWidth = 0.5;

    // Draw grid lines
    const gridSpacing = 20.0;
    for (double i = 0; i < size.width; i += gridSpacing) {
      canvas.drawLine(Offset(i, 0), Offset(i, size.height), gridPaint);
    }
    for (double i = 0; i < size.height; i += gridSpacing) {
      canvas.drawLine(Offset(0, i), Offset(size.width, i), gridPaint);
    }

    // Draw max RSL line
    final maxY = size.height * 0.1;
    canvas.drawLine(
      Offset(0, maxY),
      Offset(size.width, maxY),
      Paint()
        ..color = Colors.green[400]!
        ..strokeWidth = 2
        ..style = PaintingStyle.stroke,
    );

    // Draw current RSL level line
    final rslRange = maxRSL - (-100.0);
    final currentRSLNormalized = (maxRSL - currentRSL) / rslRange;
    final currentY =
        size.height * 0.1 + (currentRSLNormalized * (size.height * 0.8));

    // Draw dashed line for current RSL
    final dashPaint = Paint()
      ..color = Colors.red[600]!
      ..strokeWidth = 2.5
      ..style = PaintingStyle.stroke;

    const dashWidth = 5.0;
    const dashSpace = 5.0;
    double xPos = 0;
    while (xPos < size.width) {
      canvas.drawLine(
        Offset(xPos, currentY),
        Offset((xPos + dashWidth).clamp(0, size.width), currentY),
        dashPaint,
      );
      xPos += dashWidth + dashSpace;
    }

    // Create adaptive sine wave based on actual RSL
    final path = Path();
    final baseAmplitude = size.height * 0.25;
    const frequency = 0.02;

    for (double x = 0; x < size.width; x++) {
      // Normalize RSL: 0 = worst (-100 dBm), 1 = best (maxRSL)
      final rslFactor = (maxRSL - currentRSL) / rslRange;

      // Wave amplitude decreases as signal improves (more stable signal = flatter line)
      final amplitude = baseAmplitude * (rslFactor * 0.7 + 0.1);

      // Oscillate around the current RSL line
      final baseWave = amplitude * sin(x * frequency);
      final y = currentY + baseWave;

      if (x == 0) {
        path.moveTo(x, y);
      } else {
        path.lineTo(x, y);
      }
    }

    // Draw the fill under the curve
    final fillPath = Path.from(path);
    fillPath.lineTo(size.width, size.height);
    fillPath.lineTo(0, size.height);
    fillPath.close();
    canvas.drawPath(fillPath, fillPaint);

    // Draw the signal waveform
    canvas.drawPath(path, paint);

    // Draw legend
    const legendX = 12.0;
    const legendY = 8.0;
    const legendItemHeight = 16.0;

    // Green line legend (Max RSL)
    canvas.drawLine(
      const Offset(legendX, legendY),
      const Offset(legendX + 10, legendY),
      Paint()
        ..color = Colors.green[400]!
        ..strokeWidth = 2,
    );
    final maxLabel = TextPainter(
      text: TextSpan(
        text: 'Max: ${maxRSL.toStringAsFixed(1)} dBm',
        style: const TextStyle(
          color: Colors.black87,
          fontSize: 10,
          fontWeight: FontWeight.w500,
        ),
      ),
      textDirection: TextDirection.ltr,
    );
    maxLabel.layout();
    maxLabel.paint(canvas, const Offset(legendX + 14, legendY - 6));

    // Red dashed line legend (Current RSL)
    final dashedLinePaint = Paint()
      ..color = Colors.red[600]!
      ..strokeWidth = 2;

    const legendDashWidth = 3.0;
    const legendDashSpace = 3.0;
    double xLegend = legendX;
    while (xLegend < legendX + 10) {
      canvas.drawLine(
        Offset(xLegend, legendY + legendItemHeight),
        Offset((xLegend + legendDashWidth).clamp(legendX, legendX + 10),
            legendY + legendItemHeight),
        dashedLinePaint,
      );
      xLegend += legendDashWidth + legendDashSpace;
    }
    final currentLabel = TextPainter(
      text: TextSpan(
        text: 'Current: ${currentRSL.toStringAsFixed(1)} dBm',
        style: const TextStyle(
          color: Colors.black87,
          fontSize: 10,
          fontWeight: FontWeight.w500,
        ),
      ),
      textDirection: TextDirection.ltr,
    );
    currentLabel.layout();
    currentLabel.paint(
        canvas, const Offset(legendX + 14, legendY + legendItemHeight - 6));
  }

  @override
  bool shouldRepaint(SineWavePainter oldDelegate) {
    return oldDelegate.currentRSL != currentRSL || oldDelegate.maxRSL != maxRSL;
  }
}
