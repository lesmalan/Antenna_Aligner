import 'package:flutter/material.dart';
import 'dart:async' show TimeoutException;
import 'dart:math' show sin, max;
import 'dart:convert';
import 'dart:io';
import 'package:web_socket_channel/web_socket_channel.dart';
import 'package:file_picker/file_picker.dart';

/// Data point from sweep containing degree position and amplitude (RSL)
class SweepDataPoint {
  final double degree;
  final double amplitude; // RSL in dBm

  SweepDataPoint({required this.degree, required this.amplitude});

  @override
  String toString() =>
      'SweepDataPoint(degree: $degree, amplitude: $amplitude dBm)';
}

void main() {
  runApp(const MyApp());
}

enum AlignmentStep { azimuth, elevation, finalized }

enum AzimuthPhase {
  waitingForConnection,
  sweepInProgress,
  sweepComplete,
  aligned,
}

enum ElevationPhase { waitingForStart, sweepInProgress, sweepComplete, aligned }

enum OverrideView {
  connection,
  azimuthSweep,
  elevationSweep,
  alignment,
  completed,
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Microwave Signal Alignment',
      theme: ThemeData(
        useMaterial3: true,
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF1B5E20), // Dark green
          brightness: Brightness.light,
        ).copyWith(secondary: const Color(0xFFFF8F00)), // Deep amber
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
  WebSocketChannel? _channel;
  bool _isConnected = false;
  String _connectionStatus = 'Connecting to Raspberry Pi...';

  // Azimuth sweep data collection
  AzimuthPhase _azimuthPhase = AzimuthPhase.waitingForConnection;
  final List<SweepDataPoint> _azimuthSweepData =
      []; // Store all degree+RSL readings during azimuth sweep
  double _azimuthMaxSweepRSL = -100.0; // Max RSL found during azimuth sweep
  double _azimuthMaxSweepDegree = 0.0; // Degree position of max RSL
  double _azimuthCurrentDegree = 0.0; // Current azimuth degree position
  double _azimuthDegreesToMaxRSL =
      0.0; // Calculated: degrees to rotate to reach max RSL
  bool _isRecordingAzimuth = false; // Flag: continuously recording azimuth data
  bool _azimuthDataLoaded = false; // Flag: CSV data has been loaded

  // Elevation sweep data collection
  ElevationPhase _elevationPhase = ElevationPhase.waitingForStart;
  final List<SweepDataPoint> _elevationSweepData =
      []; // Store all degree+RSL readings during elevation sweep
  double _elevationMaxSweepRSL = -100.0; // Max RSL found during elevation sweep
  double _elevationMaxSweepDegree = 0.0; // Degree position of max RSL
  double _elevationCurrentDegree = 0.0; // Current elevation degree position
  double _elevationDegreesToMaxRSL =
      0.0; // Calculated: degrees to rotate to reach max RSL
  bool _isRecordingElevation =
      false; // Flag: continuously recording elevation data
  bool _elevationDataLoaded = false; // Flag: CSV data has been loaded

  // Signal data from Raspberry Pi
  double _currentRSL = -85.5; // dBm
  final double _maxRSL = -75.0; // dBm
  double _azimuthDegreesLeft = 0.0; // Degrees to rotate left to reach max
  double _azimuthDegreesRight = 0.0; // Degrees to rotate right to reach max
  double _elevationDegreesUp = 0.0; // Degrees to rotate up to reach max
  double _elevationDegreesDown = 0.0; // Degrees to rotate down to reach max

  AlignmentStep _currentStep = AlignmentStep.azimuth;
  bool _azimuthConfirmed = false;
  bool _elevationConfirmed = false;
  int _currentSide = 1; // Track which side we're aligning (1 or 2)
  bool _side1Complete = false; // Track if side 1 alignment is done
  bool _processCompleted = false; // true when the entire process is finalized

  bool _overrideMode = false;
  OverrideView _overrideView = OverrideView.connection;
  bool _isConnecting = false;

  @override
  void initState() {
    super.initState();
    // Defer connection significantly to let the UI fully render first
    // This prevents ANR (App Not Responding) issues on slow emulators
    Future.delayed(const Duration(seconds: 2), () {
      if (mounted) _connectWebSocket();
    });
  }

  Future<void> _connectWebSocket() async {
    if (_isConnecting || !mounted) return;
    _isConnecting = true;

    try {
      if (mounted) {
        setState(() {
          _connectionStatus = 'Attempting to connect...';
        });
      }

      // Create the WebSocket channel in an async context
      final channel = WebSocketChannel.connect(
        Uri.parse('ws://192.168.15.192:8000/ws'),
      );

      // Wait for the connection to be ready with a shorter timeout
      await channel.ready.timeout(
        const Duration(seconds: 3),
        onTimeout: () {
          channel.sink.close();
          throw TimeoutException('Connection timed out');
        },
      );

      if (!mounted) {
        channel.sink.close();
        return;
      }

      _channel = channel;

      if (!mounted) return;

      // Mark as connected once the stream is ready
      setState(() {
        _connectionStatus = 'Connected - waiting for data...';
      });

      // Send a request to prompt the server to start sending data
      _channel?.sink.add(jsonEncode({'action': 'start', 'request': 'rsl'}));

      _channel?.stream.listen(
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
                _azimuthSweepData.clear();
                _azimuthMaxSweepRSL = -100.0;
              }

              // Update RSL if provided
              if (data.containsKey('rsl')) {
                _currentRSL = (data['rsl'] as num).toDouble();
              }

              // Update degree positions if provided
              if (data.containsKey('azimuth_degree')) {
                _azimuthCurrentDegree = (data['azimuth_degree'] as num)
                    .toDouble();
              }
              if (data.containsKey('elevation_degree')) {
                _elevationCurrentDegree = (data['elevation_degree'] as num)
                    .toDouble();
              }

              // Handle sweep data from Pi 5 (automatic mode - no CSV upload needed)
              if (data.containsKey('sweep_active') &&
                  data['sweep_active'] == true) {
                final sweepType = data['sweep_type'] as String?;
                if (data.containsKey('sweep_point')) {
                  final point = data['sweep_point'];
                  final degree = (point['degree'] as num).toDouble();
                  final amplitude = (point['amplitude'] as num).toDouble();

                  if (sweepType == 'azimuth') {
                    // Auto-start azimuth sweep if not already
                    if (_azimuthPhase != AzimuthPhase.sweepInProgress) {
                      _azimuthPhase = AzimuthPhase.sweepInProgress;
                      _azimuthSweepData.clear();
                      _azimuthMaxSweepRSL = -100.0;
                    }
                    _azimuthSweepData.add(
                      SweepDataPoint(degree: degree, amplitude: amplitude),
                    );
                    if (amplitude > _azimuthMaxSweepRSL) {
                      _azimuthMaxSweepRSL = amplitude;
                      _azimuthMaxSweepDegree = degree;
                    }
                  } else if (sweepType == 'elevation') {
                    // Auto-start elevation sweep if not already
                    if (_elevationPhase != ElevationPhase.sweepInProgress) {
                      _elevationPhase = ElevationPhase.sweepInProgress;
                      _elevationSweepData.clear();
                      _elevationMaxSweepRSL = -100.0;
                    }
                    _elevationSweepData.add(
                      SweepDataPoint(degree: degree, amplitude: amplitude),
                    );
                    if (amplitude > _elevationMaxSweepRSL) {
                      _elevationMaxSweepRSL = amplitude;
                      _elevationMaxSweepDegree = degree;
                    }
                  }
                }
              }

              // Handle sweep completion from Pi 5
              if (data.containsKey('sweep_status') &&
                  data['sweep_status'] == 'completed') {
                final sweepType = data['sweep_type'] as String?;
                // Process bulk sweep data if provided
                if (data.containsKey('sweep_data')) {
                  final sweepDataList = data['sweep_data'] as List;
                  if (sweepType == 'azimuth') {
                    _azimuthSweepData.clear();
                    _azimuthMaxSweepRSL = -100.0;
                    for (final point in sweepDataList) {
                      final degree = (point['degree'] as num).toDouble();
                      final amplitude = (point['amplitude'] as num).toDouble();
                      _azimuthSweepData.add(
                        SweepDataPoint(degree: degree, amplitude: amplitude),
                      );
                      if (amplitude > _azimuthMaxSweepRSL) {
                        _azimuthMaxSweepRSL = amplitude;
                        _azimuthMaxSweepDegree = degree;
                      }
                    }
                  } else if (sweepType == 'elevation') {
                    _elevationSweepData.clear();
                    _elevationMaxSweepRSL = -100.0;
                    for (final point in sweepDataList) {
                      final degree = (point['degree'] as num).toDouble();
                      final amplitude = (point['amplitude'] as num).toDouble();
                      _elevationSweepData.add(
                        SweepDataPoint(degree: degree, amplitude: amplitude),
                      );
                      if (amplitude > _elevationMaxSweepRSL) {
                        _elevationMaxSweepRSL = amplitude;
                        _elevationMaxSweepDegree = degree;
                      }
                    }
                  }
                }
                // Mark sweep as complete
                if (sweepType == 'azimuth' && _azimuthSweepData.isNotEmpty) {
                  _azimuthPhase = AzimuthPhase.sweepComplete;
                  _azimuthDataLoaded = true;
                  _calculateAzimuthDegreesToMax();
                } else if (sweepType == 'elevation' &&
                    _elevationSweepData.isNotEmpty) {
                  _elevationPhase = ElevationPhase.sweepComplete;
                  _elevationDataLoaded = true;
                  _calculateElevationDegreesToMax();
                }
              }

              // Legacy: manual recording mode (fallback if no auto sweep data)
              if (_isRecordingAzimuth &&
                  _azimuthPhase == AzimuthPhase.sweepInProgress) {
                _azimuthSweepData.add(
                  SweepDataPoint(
                    degree: _azimuthCurrentDegree,
                    amplitude: _currentRSL,
                  ),
                );
                if (_currentRSL > _azimuthMaxSweepRSL) {
                  _azimuthMaxSweepRSL = _currentRSL;
                  _azimuthMaxSweepDegree = _azimuthCurrentDegree;
                }
              }

              // Legacy: manual recording mode (fallback if no auto sweep data)
              if (_isRecordingElevation &&
                  _elevationPhase == ElevationPhase.sweepInProgress) {
                _elevationSweepData.add(
                  SweepDataPoint(
                    degree: _elevationCurrentDegree,
                    amplitude: _currentRSL,
                  ),
                );
                if (_currentRSL > _elevationMaxSweepRSL) {
                  _elevationMaxSweepRSL = _currentRSL;
                  _elevationMaxSweepDegree = _elevationCurrentDegree;
                }
              }

              // Update degree rotation hints if provided by server
              if (data.containsKey('azimuth_degrees_left')) {
                _azimuthDegreesLeft = (data['azimuth_degrees_left'] as num)
                    .toDouble();
              }
              if (data.containsKey('azimuth_degrees_right')) {
                _azimuthDegreesRight = (data['azimuth_degrees_right'] as num)
                    .toDouble();
              }
              if (data.containsKey('elevation_degrees_up')) {
                _elevationDegreesUp = (data['elevation_degrees_up'] as num)
                    .toDouble();
              }
              if (data.containsKey('elevation_degrees_down')) {
                _elevationDegreesDown = (data['elevation_degrees_down'] as num)
                    .toDouble();
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
          _isConnecting = false;
        },
        onDone: () {
          if (mounted) {
            setState(() {
              _isConnected = false;
              _connectionStatus = 'Connection closed';
            });
          }
          _isConnecting = false;
          // Attempt to reconnect after 3 seconds
          Future.delayed(const Duration(seconds: 3), _connectWebSocket);
        },
      );
    } catch (e) {
      _isConnecting = false;
      if (mounted) {
        setState(() {
          _isConnected = false;
          _connectionStatus = 'Failed to connect: $e';
        });
      }
      debugPrint('WebSocket connection error: $e');
      // Attempt to reconnect after 5 seconds
      Future.delayed(const Duration(seconds: 5), _connectWebSocket);
    }
  }

  @override
  void dispose() {
    _channel?.sink.close();
    super.dispose();
  }

  /// Load azimuth sweep data from CSV file
  Future<void> _loadAzimuthCSV() async {
    try {
      final result = await FilePicker.platform.pickFiles(
        type: FileType.custom,
        allowedExtensions: ['csv'],
        dialogTitle: 'Select Azimuth Sweep CSV File',
      );

      if (result != null && result.files.single.path != null) {
        final file = File(result.files.single.path!);
        await _parseCSVFile(file, isAzimuth: true);
      }
    } catch (e) {
      debugPrint('Error loading azimuth CSV: $e');
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text('Error loading CSV: $e')));
      }
    }
  }

  /// Load elevation sweep data from CSV file
  Future<void> _loadElevationCSV() async {
    try {
      final result = await FilePicker.platform.pickFiles(
        type: FileType.custom,
        allowedExtensions: ['csv'],
        dialogTitle: 'Select Elevation Sweep CSV File',
      );

      if (result != null && result.files.single.path != null) {
        final file = File(result.files.single.path!);
        await _parseCSVFile(file, isAzimuth: false);
      }
    } catch (e) {
      debugPrint('Error loading elevation CSV: $e');
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text('Error loading CSV: $e')));
      }
    }
  }

  /// Parse CSV file and extract degree + amplitude data
  /// Expected columns: azimuth_steps or elevation_steps, amplitude_dB or Amplitude_Smoothed_dB
  Future<void> _parseCSVFile(File file, {required bool isAzimuth}) async {
    try {
      final lines = await file.readAsLines();
      if (lines.isEmpty) {
        throw Exception('CSV file is empty');
      }

      // Parse header to find column indices
      final header = lines[0].toLowerCase().split(',');
      int degreeColIndex = -1;
      int amplitudeColIndex = -1;

      for (int i = 0; i < header.length; i++) {
        final col = header[i].trim();
        // Look for degree columns
        if (col.contains('azimuth') ||
            col.contains('elevation') ||
            col.contains('degree') ||
            col.contains('steps')) {
          if (isAzimuth && (col.contains('azimuth') || degreeColIndex == -1)) {
            degreeColIndex = i;
          } else if (!isAzimuth &&
              (col.contains('elevation') || degreeColIndex == -1)) {
            degreeColIndex = i;
          }
        }
        // Look for amplitude columns - prefer smoothed
        if (col.contains('smoothed') || col.contains('amplitude')) {
          if (col.contains('smoothed') || amplitudeColIndex == -1) {
            amplitudeColIndex = i;
          }
        }
      }

      if (degreeColIndex == -1 || amplitudeColIndex == -1) {
        throw Exception(
          'Could not find required columns (degree and amplitude) in CSV',
        );
      }

      final dataPoints = <SweepDataPoint>[];
      double maxAmplitude = -100.0;
      double maxDegree = 0.0;

      // Parse data rows
      for (int i = 1; i < lines.length; i++) {
        final parts = lines[i].split(',');
        if (parts.length > max(degreeColIndex, amplitudeColIndex)) {
          final degree = double.tryParse(parts[degreeColIndex].trim());
          final amplitude = double.tryParse(parts[amplitudeColIndex].trim());

          if (degree != null && amplitude != null) {
            dataPoints.add(
              SweepDataPoint(degree: degree, amplitude: amplitude),
            );
            if (amplitude > maxAmplitude) {
              maxAmplitude = amplitude;
              maxDegree = degree;
            }
          }
        }
      }

      if (dataPoints.isEmpty) {
        throw Exception('No valid data points found in CSV');
      }

      setState(() {
        if (isAzimuth) {
          _azimuthSweepData.clear();
          _azimuthSweepData.addAll(dataPoints);
          _azimuthMaxSweepRSL = maxAmplitude;
          _azimuthMaxSweepDegree = maxDegree;
          _azimuthDataLoaded = true;
          _azimuthPhase = AzimuthPhase.sweepComplete;
          _calculateAzimuthDegreesToMax();
        } else {
          _elevationSweepData.clear();
          _elevationSweepData.addAll(dataPoints);
          _elevationMaxSweepRSL = maxAmplitude;
          _elevationMaxSweepDegree = maxDegree;
          _elevationDataLoaded = true;
          _elevationPhase = ElevationPhase.sweepComplete;
          _calculateElevationDegreesToMax();
        }
      });

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              'Loaded ${dataPoints.length} data points. Max RSL: ${maxAmplitude.toStringAsFixed(1)} dBm at ${maxDegree.toStringAsFixed(1)}°',
            ),
            backgroundColor: Colors.green,
          ),
        );
      }
    } catch (e) {
      debugPrint('Error parsing CSV: $e');
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Error parsing CSV: $e'),
            backgroundColor: Colors.red,
          ),
        );
      }
    }
  }

  /// Calculate degrees to rotate to reach max RSL for azimuth
  void _calculateAzimuthDegreesToMax() {
    if (_azimuthSweepData.isEmpty) return;

    // Get current position (last data point if from live recording, or use 0 as starting point)
    final currentDegree = _azimuthCurrentDegree;
    final targetDegree = _azimuthMaxSweepDegree;

    _azimuthDegreesToMaxRSL = targetDegree - currentDegree;

    // Update directional hints
    if (_azimuthDegreesToMaxRSL > 0) {
      _azimuthDegreesRight = _azimuthDegreesToMaxRSL;
      _azimuthDegreesLeft = 0;
    } else {
      _azimuthDegreesLeft = _azimuthDegreesToMaxRSL.abs();
      _azimuthDegreesRight = 0;
    }
  }

  /// Calculate degrees to rotate to reach max RSL for elevation
  void _calculateElevationDegreesToMax() {
    if (_elevationSweepData.isEmpty) return;

    // Get current position (last data point if from live recording, or use 0 as starting point)
    final currentDegree = _elevationCurrentDegree;
    final targetDegree = _elevationMaxSweepDegree;

    _elevationDegreesToMaxRSL = targetDegree - currentDegree;

    // Update directional hints
    if (_elevationDegreesToMaxRSL > 0) {
      _elevationDegreesUp = _elevationDegreesToMaxRSL;
      _elevationDegreesDown = 0;
    } else {
      _elevationDegreesDown = _elevationDegreesToMaxRSL.abs();
      _elevationDegreesUp = 0;
    }
  }

  void _setOverrideView(OverrideView view) {
    setState(() {
      _overrideMode = true;
      _overrideView = view;
      _currentRSL = -85.0;

      switch (view) {
        case OverrideView.connection:
          _azimuthPhase = AzimuthPhase.waitingForConnection;
          _elevationPhase = ElevationPhase.waitingForStart;
          _processCompleted = false;
          _currentStep = AlignmentStep.azimuth;
          break;
        case OverrideView.azimuthSweep:
          _azimuthPhase = AzimuthPhase.sweepInProgress;
          _elevationPhase = ElevationPhase.waitingForStart;
          _processCompleted = false;
          _currentStep = AlignmentStep.azimuth;
          _seedAzimuthDemoData();
          break;
        case OverrideView.elevationSweep:
          _azimuthPhase = AzimuthPhase.aligned;
          _elevationPhase = ElevationPhase.sweepInProgress;
          _processCompleted = false;
          _currentStep = AlignmentStep.elevation;
          _seedElevationDemoData();
          break;
        case OverrideView.alignment:
          _azimuthPhase = AzimuthPhase.aligned;
          _elevationPhase = ElevationPhase.waitingForStart;
          _azimuthConfirmed = true;
          _elevationConfirmed = false;
          _processCompleted = false;
          _currentStep = AlignmentStep.elevation;
          _seedAzimuthDemoData();
          break;
        case OverrideView.completed:
          _azimuthPhase = AzimuthPhase.aligned;
          _elevationPhase = ElevationPhase.aligned;
          _processCompleted = true;
          _currentStep = AlignmentStep.finalized;
          break;
      }
    });
  }

  void _seedAzimuthDemoData() {
    _azimuthSweepData
      ..clear()
      ..addAll([
        SweepDataPoint(degree: -40, amplitude: -95.0),
        SweepDataPoint(degree: -30, amplitude: -92.0),
        SweepDataPoint(degree: -20, amplitude: -90.5),
        SweepDataPoint(degree: -10, amplitude: -88.0),
        SweepDataPoint(degree: 0, amplitude: -86.0),
        SweepDataPoint(degree: 10, amplitude: -84.0),
        SweepDataPoint(degree: 20, amplitude: -83.0), // Max RSL at 20°
        SweepDataPoint(degree: 30, amplitude: -84.5),
      ]);
    _azimuthMaxSweepRSL = -83.0;
    _azimuthMaxSweepDegree = 20.0;
    _azimuthCurrentDegree = 30.0; // Currently at end of sweep
    _azimuthDegreesToMaxRSL = -10.0; // Need to go back 10° left
    _azimuthDegreesLeft = 10.0;
    _azimuthDegreesRight = 0.0;
    _azimuthDataLoaded = true;
  }

  void _seedElevationDemoData() {
    _elevationSweepData
      ..clear()
      ..addAll([
        SweepDataPoint(degree: -20, amplitude: -96.0),
        SweepDataPoint(degree: -15, amplitude: -94.0),
        SweepDataPoint(degree: -10, amplitude: -91.0),
        SweepDataPoint(degree: -5, amplitude: -89.5),
        SweepDataPoint(degree: 0, amplitude: -87.0),
        SweepDataPoint(degree: 5, amplitude: -85.0),
        SweepDataPoint(degree: 10, amplitude: -83.5), // Max RSL at 10°
        SweepDataPoint(degree: 15, amplitude: -84.0),
      ]);
    _elevationMaxSweepRSL = -83.5;
    _elevationMaxSweepDegree = 10.0;
    _elevationCurrentDegree = 15.0; // Currently at end of sweep
    _elevationDegreesToMaxRSL = -5.0; // Need to go down 5°
    _elevationDegreesDown = 5.0;
    _elevationDegreesUp = 0.0;
    _elevationDataLoaded = true;
  }

  void _disableOverride() {
    setState(() {
      _overrideMode = false;
      _overrideView = OverrideView.connection;
    });
  }

  List<OverrideView> get _overrideOrder => const [
    OverrideView.connection,
    OverrideView.azimuthSweep,
    OverrideView.elevationSweep,
    OverrideView.alignment,
    OverrideView.completed,
  ];

  void _goToNextOverrideStep() {
    final currentIndex = _overrideOrder.indexOf(_overrideView);
    if (currentIndex < _overrideOrder.length - 1) {
      _setOverrideView(_overrideOrder[currentIndex + 1]);
    }
  }

  void _goToPreviousOverrideStep() {
    final currentIndex = _overrideOrder.indexOf(_overrideView);
    if (currentIndex > 0) {
      _setOverrideView(_overrideOrder[currentIndex - 1]);
    }
  }

  Widget _buildDebugNavBar() {
    final currentIndex = _overrideOrder.indexOf(_overrideView);
    return SafeArea(
      top: false,
      child: BottomAppBar(
        color: Colors.grey[100],
        child: SizedBox(
          height: 44,
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 0),
            child: Row(
              children: [
                IconButton(
                  iconSize: 20,
                  padding: const EdgeInsets.all(4),
                  tooltip: 'Previous Step',
                  onPressed: currentIndex > 0
                      ? _goToPreviousOverrideStep
                      : null,
                  icon: const Icon(Icons.chevron_left),
                ),
                Flexible(
                  child: Text(
                    'Debug Step: ${_overrideView.name}',
                    textAlign: TextAlign.center,
                    overflow: TextOverflow.ellipsis,
                    maxLines: 1,
                    style: Theme.of(context).textTheme.labelLarge?.copyWith(
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
                IconButton(
                  iconSize: 20,
                  padding: const EdgeInsets.all(4),
                  tooltip: 'Next Step',
                  onPressed: currentIndex < _overrideOrder.length - 1
                      ? _goToNextOverrideStep
                      : null,
                  icon: const Icon(Icons.chevron_right),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  void _showOverrideMenu() {
    showModalBottomSheet(
      context: context,
      builder: (context) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ListTile(
              leading: const Icon(Icons.link_off),
              title: const Text('Connection Screen'),
              onTap: () {
                Navigator.pop(context);
                _setOverrideView(OverrideView.connection);
              },
            ),
            ListTile(
              leading: const Icon(Icons.explore),
              title: const Text('Azimuth Sweep'),
              onTap: () {
                Navigator.pop(context);
                _setOverrideView(OverrideView.azimuthSweep);
              },
            ),
            ListTile(
              leading: const Icon(Icons.height),
              title: const Text('Elevation Sweep'),
              onTap: () {
                Navigator.pop(context);
                _setOverrideView(OverrideView.elevationSweep);
              },
            ),
            ListTile(
              leading: const Icon(Icons.dashboard),
              title: const Text('Alignment Screen'),
              onTap: () {
                Navigator.pop(context);
                _setOverrideView(OverrideView.alignment);
              },
            ),
            ListTile(
              leading: const Icon(Icons.check_circle),
              title: const Text('Completed Screen'),
              onTap: () {
                Navigator.pop(context);
                _setOverrideView(OverrideView.completed);
              },
            ),
            const Divider(),
            ListTile(
              leading: Icon(_overrideMode ? Icons.stop_circle : Icons.tune),
              title: Text(
                _overrideMode ? 'Disable Override' : 'Enable Override',
              ),
              onTap: () {
                Navigator.pop(context);
                if (_overrideMode) {
                  _disableOverride();
                } else {
                  _setOverrideView(OverrideView.alignment);
                }
              },
            ),
          ],
        ),
      ),
    );
  }

  IconButton _buildOverrideButton() {
    return IconButton(
      tooltip: _overrideMode ? 'Override Mode (On)' : 'Override Mode',
      icon: Icon(_overrideMode ? Icons.tune : Icons.tune_outlined),
      onPressed: _showOverrideMenu,
    );
  }

  @override
  Widget build(BuildContext context) {
    // Show connection screen if not yet connected
    if ((!_isConnected && !_overrideMode) ||
        (_overrideMode && _overrideView == OverrideView.connection)) {
      return Scaffold(
        bottomNavigationBar: _overrideMode ? _buildDebugNavBar() : null,
        body: Container(
          decoration: BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: [
                Theme.of(context).colorScheme.primary,
                Colors.green[900]!,
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
                  'IP: 192.168.15.192:8000',
                  style: Theme.of(
                    context,
                  ).textTheme.bodyMedium?.copyWith(color: Colors.white70),
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
                const SizedBox(height: 24),
                ElevatedButton.icon(
                  onPressed: _showOverrideMenu,
                  icon: Icon(_overrideMode ? Icons.tune : Icons.tune_outlined),
                  label: Text(
                    _overrideMode ? 'Override Menu' : 'Override / Demo Mode',
                  ),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.white,
                    foregroundColor: Theme.of(context).colorScheme.primary,
                  ),
                ),
              ],
            ),
          ),
        ),
      );
    }

    if (_overrideMode && _overrideView == OverrideView.azimuthSweep) {
      return _buildAzimuthSweepScreen();
    }

    if (_overrideMode && _overrideView == OverrideView.elevationSweep) {
      return _buildElevationSweepScreen();
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
        bottomNavigationBar: _overrideMode ? _buildDebugNavBar() : null,
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
            child: Padding(
              padding: const EdgeInsets.all(24),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  const Icon(
                    Icons.check_circle,
                    size: 120,
                    color: Colors.white,
                  ),
                  const SizedBox(height: 32),
                  Text(
                    'Alignment Finalized!',
                    style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                      color: Colors.white,
                      fontWeight: FontWeight.bold,
                    ),
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: 16),
                  Text(
                    'Both Side 1 and Side 2 antennas have been successfully aligned.',
                    style: Theme.of(
                      context,
                    ).textTheme.titleMedium?.copyWith(color: Colors.white),
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: 24),
                  Container(
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: Colors.white.withValues(alpha: 0.2),
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: Colors.white54),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const Icon(
                          Icons.link_off,
                          color: Colors.white,
                          size: 28,
                        ),
                        const SizedBox(width: 12),
                        Text(
                          'Disconnect from Side 2 antenna',
                          style: TextStyle(
                            color: Colors.white,
                            fontWeight: FontWeight.bold,
                            fontSize: 16,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
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
          _buildOverrideButton(),
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
                      color: _isConnected ? Colors.green[500] : Colors.red[300],
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
        child: LayoutBuilder(
          builder: (context, constraints) {
            return SingleChildScrollView(
              child: ConstrainedBox(
                constraints: BoxConstraints(
                  minHeight: constraints.maxHeight,
                  maxWidth: 800,
                ),
                child: Center(
                  child: SizedBox(
                    width: constraints.maxWidth > 800
                        ? 800
                        : constraints.maxWidth,
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        // Signal Graph Section
                        SizedBox(
                          height: 300,
                          child: _buildSignalGraphSection(),
                        ),

                        // Divider
                        const Padding(
                          padding: EdgeInsets.symmetric(horizontal: 16),
                          child: Divider(thickness: 2),
                        ),

                        // Alignment Information Section
                        _buildAlignmentInfoSection(),

                        // Control Buttons Section
                        _buildControlButtonsSection(),
                      ],
                    ),
                  ),
                ),
              ),
            );
          },
        ),
      ),
      bottomNavigationBar: _overrideMode ? _buildDebugNavBar() : null,
    );
  }

  Widget _buildAzimuthSweepScreen() {
    if (_azimuthPhase == AzimuthPhase.sweepInProgress) {
      return Scaffold(
        appBar: AppBar(
          title: Text('Azimuth Sweep - Side $_currentSide'),
          backgroundColor: Theme.of(context).colorScheme.primary,
          foregroundColor: Colors.white,
          actions: [_buildOverrideButton()],
        ),
        bottomNavigationBar: _overrideMode ? _buildDebugNavBar() : null,
        body: SafeArea(
          child: SingleChildScrollView(
            child: Center(
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 800),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    // Side 1 complete indicator (only show when on side 2)
                    if (_side1Complete)
                      Container(
                        width: double.infinity,
                        padding: const EdgeInsets.all(12),
                        color: Colors.green[100],
                        child: Row(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Icon(
                              Icons.check_circle,
                              color: Colors.green[700],
                              size: 20,
                            ),
                            const SizedBox(width: 8),
                            Text(
                              'Side 1 Complete',
                              style: TextStyle(
                                color: Colors.green[700],
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                          ],
                        ),
                      ),
                    // Instructions
                    Container(
                      width: double.infinity,
                      padding: const EdgeInsets.all(16),
                      color: Colors.amber[100],
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Icon(Icons.info, size: 40, color: Colors.amber[700]),
                          const SizedBox(height: 12),
                          Text(
                            'Azimuth Sweep in Progress - Side $_currentSide',
                            style: Theme.of(context).textTheme.titleMedium
                                ?.copyWith(
                                  fontWeight: FontWeight.bold,
                                  color: Colors.black87,
                                ),
                          ),
                          const SizedBox(height: 8),
                          Text(
                            'Rotate the antenna from left to right. Press "Start Recording" to begin capturing data.',
                            style: Theme.of(context).textTheme.bodyMedium
                                ?.copyWith(color: Colors.black54),
                            textAlign: TextAlign.center,
                          ),
                        ],
                      ),
                    ),
                    // Real-time signal graph
                    SizedBox(height: 250, child: _buildSignalGraphSection()),
                    // Sweep data info
                    Container(
                      width: double.infinity,
                      padding: const EdgeInsets.all(16),
                      color: Colors.grey[100],
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Wrap(
                            spacing: 24,
                            runSpacing: 16,
                            alignment: WrapAlignment.spaceEvenly,
                            children: [
                              Column(
                                mainAxisSize: MainAxisSize.min,
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
                                    '${_azimuthSweepData.length}',
                                    style: Theme.of(context)
                                        .textTheme
                                        .titleLarge
                                        ?.copyWith(fontWeight: FontWeight.bold),
                                  ),
                                ],
                              ),
                              Column(
                                mainAxisSize: MainAxisSize.min,
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
                                        .titleLarge
                                        ?.copyWith(
                                          fontWeight: FontWeight.bold,
                                          color: Colors.green[700],
                                        ),
                                  ),
                                ],
                              ),
                              Column(
                                mainAxisSize: MainAxisSize.min,
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
                                        .titleLarge
                                        ?.copyWith(fontWeight: FontWeight.bold),
                                  ),
                                ],
                              ),
                            ],
                          ),
                          const SizedBox(height: 20),
                          Wrap(
                            spacing: 12,
                            runSpacing: 12,
                            alignment: WrapAlignment.center,
                            children: [
                              ElevatedButton.icon(
                                onPressed: _toggleAzimuthRecording,
                                icon: Icon(
                                  _isRecordingAzimuth
                                      ? Icons.stop
                                      : Icons.play_arrow,
                                ),
                                label: Text(
                                  _isRecordingAzimuth
                                      ? 'Stop Recording'
                                      : 'Start Recording',
                                ),
                                style: ElevatedButton.styleFrom(
                                  backgroundColor: _isRecordingAzimuth
                                      ? Colors.red[600]
                                      : Theme.of(context).colorScheme.primary,
                                  foregroundColor: Colors.white,
                                  padding: const EdgeInsets.symmetric(
                                    horizontal: 24,
                                    vertical: 12,
                                  ),
                                ),
                              ),
                              ElevatedButton.icon(
                                onPressed: _completeSweep,
                                icon: const Icon(Icons.check),
                                label: const Text('Sweep Complete'),
                                style: ElevatedButton.styleFrom(
                                  backgroundColor: Colors.green[600],
                                  foregroundColor: Colors.white,
                                  padding: const EdgeInsets.symmetric(
                                    horizontal: 24,
                                    vertical: 12,
                                  ),
                                ),
                              ),
                            ],
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      );
    }

    // Sweep complete - show degree analysis and load CSV option
    if (_azimuthPhase == AzimuthPhase.sweepComplete) {
      return Scaffold(
        appBar: AppBar(
          title: Text('Azimuth Alignment - Side $_currentSide'),
          backgroundColor: Theme.of(context).colorScheme.primary,
          foregroundColor: Colors.white,
          actions: [_buildOverrideButton()],
        ),
        bottomNavigationBar: _overrideMode ? _buildDebugNavBar() : null,
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
                          color: Colors.green[100],
                          border: Border.all(color: Colors.green[500]!),
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              children: [
                                const Icon(
                                  Icons.check_circle,
                                  color: Colors.green,
                                  size: 24,
                                ),
                                const SizedBox(width: 8),
                                Text(
                                  _azimuthDataLoaded
                                      ? 'CSV Data Loaded'
                                      : 'Sweep Complete',
                                  style: Theme.of(context).textTheme.titleMedium
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
                              style: Theme.of(context).textTheme.titleSmall
                                  ?.copyWith(fontWeight: FontWeight.bold),
                            ),
                            const SizedBox(height: 8),
                            Text(
                              'Data points collected: ${_azimuthSweepData.length}',
                              style: Theme.of(context).textTheme.bodyMedium,
                            ),
                            const SizedBox(height: 4),
                            Text(
                              'Maximum RSL: ${_azimuthMaxSweepRSL.toStringAsFixed(1)} dBm at ${_azimuthMaxSweepDegree.toStringAsFixed(1)}°',
                              style: Theme.of(context).textTheme.bodyMedium
                                  ?.copyWith(
                                    color: Colors.green[700],
                                    fontWeight: FontWeight.bold,
                                  ),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(height: 24),
                      // Data status and optional CSV fallback
                      if (!_azimuthDataLoaded) ...[
                        Container(
                          padding: const EdgeInsets.all(12),
                          decoration: BoxDecoration(
                            color: Colors.blue[50],
                            border: Border.all(color: Colors.blue[300]!),
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: Row(
                            children: [
                              Icon(Icons.wifi, color: Colors.blue[700]),
                              const SizedBox(width: 12),
                              Expanded(
                                child: Text(
                                  'Sweep data will be received automatically from Pi 5 when you run the motor control script.',
                                  style: TextStyle(color: Colors.blue[800]),
                                ),
                              ),
                            ],
                          ),
                        ),
                        const SizedBox(height: 16),
                        Text(
                          'Or load from CSV file (optional):',
                          style: Theme.of(context).textTheme.bodyMedium
                              ?.copyWith(color: Colors.grey[600]),
                        ),
                        const SizedBox(height: 8),
                        SizedBox(
                          width: double.infinity,
                          child: OutlinedButton.icon(
                            onPressed: _loadAzimuthCSV,
                            icon: const Icon(Icons.upload_file),
                            label: const Text('Load Azimuth CSV'),
                            style: OutlinedButton.styleFrom(
                              foregroundColor: Colors.grey[700],
                              padding: const EdgeInsets.symmetric(
                                horizontal: 32,
                                vertical: 12,
                              ),
                            ),
                          ),
                        ),
                        const SizedBox(height: 24),
                      ],
                      // Show alignment instructions when data is loaded
                      if (_azimuthDataLoaded) ...[
                        Container(
                          padding: const EdgeInsets.all(16),
                          decoration: BoxDecoration(
                            color: Colors.amber[100],
                            border: Border.all(color: Colors.amber[500]!),
                            borderRadius: BorderRadius.circular(12),
                          ),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                'Alignment Instructions:',
                                style: Theme.of(context).textTheme.titleSmall
                                    ?.copyWith(fontWeight: FontWeight.bold),
                              ),
                              const SizedBox(height: 12),
                              Text(
                                'Maximum signal at: ${_azimuthMaxSweepDegree.toStringAsFixed(1)}°',
                                style: Theme.of(context).textTheme.bodyMedium
                                    ?.copyWith(
                                      color: Colors.green[700],
                                      fontWeight: FontWeight.bold,
                                    ),
                              ),
                              const SizedBox(height: 8),
                              Text(
                                'Current position: ${_azimuthCurrentDegree.toStringAsFixed(1)}°',
                                style: Theme.of(context).textTheme.bodyMedium,
                              ),
                              const SizedBox(height: 12),
                              Container(
                                padding: const EdgeInsets.all(12),
                                decoration: BoxDecoration(
                                  color: Colors.orange[50],
                                  border: Border.all(
                                    color: Colors.orange[300]!,
                                  ),
                                  borderRadius: BorderRadius.circular(8),
                                ),
                                child: RichText(
                                  text: TextSpan(
                                    style: Theme.of(
                                      context,
                                    ).textTheme.bodyMedium,
                                    children: [
                                      TextSpan(
                                        text: _azimuthDegreesToMaxRSL < 0
                                            ? 'Rotate LEFT '
                                            : 'Rotate RIGHT ',
                                      ),
                                      TextSpan(
                                        text:
                                            '${_azimuthDegreesToMaxRSL.abs().toStringAsFixed(1)}°',
                                        style: const TextStyle(
                                          fontWeight: FontWeight.bold,
                                          color: Colors.orange,
                                          fontSize: 18,
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
                              backgroundColor: Theme.of(
                                context,
                              ).colorScheme.primary,
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
          title: Text('Elevation Sweep - Side $_currentSide'),
          backgroundColor: Theme.of(context).colorScheme.primary,
          foregroundColor: Colors.white,
          actions: [_buildOverrideButton()],
        ),
        bottomNavigationBar: _overrideMode ? _buildDebugNavBar() : null,
        body: SafeArea(
          child: SingleChildScrollView(
            child: Center(
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 800),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    // Side 1 complete indicator (only show when on side 2)
                    if (_side1Complete)
                      Container(
                        width: double.infinity,
                        padding: const EdgeInsets.all(12),
                        color: Colors.green[100],
                        child: Row(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Icon(
                              Icons.check_circle,
                              color: Colors.green[700],
                              size: 20,
                            ),
                            const SizedBox(width: 8),
                            Text(
                              'Side 1 Complete',
                              style: TextStyle(
                                color: Colors.green[700],
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                          ],
                        ),
                      ),
                    // Instructions
                    Container(
                      width: double.infinity,
                      padding: const EdgeInsets.all(16),
                      color: Colors.amber[100],
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Icon(Icons.info, size: 40, color: Colors.amber[700]),
                          const SizedBox(height: 12),
                          Text(
                            'Elevation Sweep in Progress - Side $_currentSide',
                            style: Theme.of(context).textTheme.titleMedium
                                ?.copyWith(
                                  fontWeight: FontWeight.bold,
                                  color: Colors.black87,
                                ),
                          ),
                          const SizedBox(height: 8),
                          Text(
                            'Rotate the antenna from bottom to top. Press "Start Recording" to begin capturing data.',
                            style: Theme.of(context).textTheme.bodyMedium
                                ?.copyWith(color: Colors.black54),
                            textAlign: TextAlign.center,
                          ),
                        ],
                      ),
                    ),
                    // Real-time signal graph
                    SizedBox(height: 250, child: _buildSignalGraphSection()),
                    // Sweep data info
                    Container(
                      width: double.infinity,
                      padding: const EdgeInsets.all(16),
                      color: Colors.grey[100],
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Wrap(
                            spacing: 24,
                            runSpacing: 16,
                            alignment: WrapAlignment.spaceEvenly,
                            children: [
                              Column(
                                mainAxisSize: MainAxisSize.min,
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
                                    '${_elevationSweepData.length}',
                                    style: Theme.of(context)
                                        .textTheme
                                        .titleLarge
                                        ?.copyWith(fontWeight: FontWeight.bold),
                                  ),
                                ],
                              ),
                              Column(
                                mainAxisSize: MainAxisSize.min,
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
                                        .titleLarge
                                        ?.copyWith(
                                          fontWeight: FontWeight.bold,
                                          color: Colors.green[700],
                                        ),
                                  ),
                                ],
                              ),
                              Column(
                                mainAxisSize: MainAxisSize.min,
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
                                        .titleLarge
                                        ?.copyWith(fontWeight: FontWeight.bold),
                                  ),
                                ],
                              ),
                            ],
                          ),
                          const SizedBox(height: 20),
                          Wrap(
                            spacing: 12,
                            runSpacing: 12,
                            alignment: WrapAlignment.center,
                            children: [
                              ElevatedButton.icon(
                                onPressed: _toggleElevationRecording,
                                icon: Icon(
                                  _isRecordingElevation
                                      ? Icons.stop
                                      : Icons.play_arrow,
                                ),
                                label: Text(
                                  _isRecordingElevation
                                      ? 'Stop Recording'
                                      : 'Start Recording',
                                ),
                                style: ElevatedButton.styleFrom(
                                  backgroundColor: _isRecordingElevation
                                      ? Colors.red[600]
                                      : Theme.of(context).colorScheme.primary,
                                  foregroundColor: Colors.white,
                                  padding: const EdgeInsets.symmetric(
                                    horizontal: 24,
                                    vertical: 12,
                                  ),
                                ),
                              ),
                              ElevatedButton.icon(
                                onPressed: _completeElevationSweep,
                                icon: const Icon(Icons.check),
                                label: const Text('Sweep Complete'),
                                style: ElevatedButton.styleFrom(
                                  backgroundColor: Colors.green[600],
                                  foregroundColor: Colors.white,
                                  padding: const EdgeInsets.symmetric(
                                    horizontal: 24,
                                    vertical: 12,
                                  ),
                                ),
                              ),
                            ],
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      );
    }

    // Elevation sweep complete - ask for number of turnbuckles
    if (_elevationPhase == ElevationPhase.sweepComplete) {
      return Scaffold(
        appBar: AppBar(
          title: Text('Elevation Alignment - Side $_currentSide'),
          backgroundColor: Theme.of(context).colorScheme.primary,
          foregroundColor: Colors.white,
          actions: [_buildOverrideButton()],
        ),
        bottomNavigationBar: _overrideMode ? _buildDebugNavBar() : null,
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
                          color: Colors.green[100],
                          border: Border.all(color: Colors.green[500]!),
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              children: [
                                const Icon(
                                  Icons.check_circle,
                                  color: Colors.green,
                                  size: 24,
                                ),
                                const SizedBox(width: 8),
                                Text(
                                  _elevationDataLoaded
                                      ? 'CSV Data Loaded'
                                      : 'Sweep Complete',
                                  style: Theme.of(context).textTheme.titleMedium
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
                              style: Theme.of(context).textTheme.titleSmall
                                  ?.copyWith(fontWeight: FontWeight.bold),
                            ),
                            const SizedBox(height: 8),
                            Text(
                              'Data points collected: ${_elevationSweepData.length}',
                              style: Theme.of(context).textTheme.bodyMedium,
                            ),
                            const SizedBox(height: 4),
                            Text(
                              'Maximum RSL: ${_elevationMaxSweepRSL.toStringAsFixed(1)} dBm at ${_elevationMaxSweepDegree.toStringAsFixed(1)}°',
                              style: Theme.of(context).textTheme.bodyMedium
                                  ?.copyWith(
                                    color: Colors.green[700],
                                    fontWeight: FontWeight.bold,
                                  ),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(height: 24),
                      // Data status and optional CSV fallback
                      if (!_elevationDataLoaded) ...[
                        Container(
                          padding: const EdgeInsets.all(12),
                          decoration: BoxDecoration(
                            color: Colors.blue[50],
                            border: Border.all(color: Colors.blue[300]!),
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: Row(
                            children: [
                              Icon(Icons.wifi, color: Colors.blue[700]),
                              const SizedBox(width: 12),
                              Expanded(
                                child: Text(
                                  'Sweep data will be received automatically from Pi 5 when you run the motor control script.',
                                  style: TextStyle(color: Colors.blue[800]),
                                ),
                              ),
                            ],
                          ),
                        ),
                        const SizedBox(height: 16),
                        Text(
                          'Or load from CSV file (optional):',
                          style: Theme.of(context).textTheme.bodyMedium
                              ?.copyWith(color: Colors.grey[600]),
                        ),
                        const SizedBox(height: 8),
                        SizedBox(
                          width: double.infinity,
                          child: OutlinedButton.icon(
                            onPressed: _loadElevationCSV,
                            icon: const Icon(Icons.upload_file),
                            label: const Text('Load Elevation CSV'),
                            style: OutlinedButton.styleFrom(
                              foregroundColor: Colors.grey[700],
                              padding: const EdgeInsets.symmetric(
                                horizontal: 32,
                                vertical: 12,
                              ),
                            ),
                          ),
                        ),
                        const SizedBox(height: 24),
                      ],
                      // Show alignment instructions when data is loaded
                      if (_elevationDataLoaded) ...[
                        Container(
                          padding: const EdgeInsets.all(16),
                          decoration: BoxDecoration(
                            color: Colors.amber[100],
                            border: Border.all(color: Colors.amber[500]!),
                            borderRadius: BorderRadius.circular(12),
                          ),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                'Alignment Instructions:',
                                style: Theme.of(context).textTheme.titleSmall
                                    ?.copyWith(fontWeight: FontWeight.bold),
                              ),
                              const SizedBox(height: 12),
                              Text(
                                'Maximum signal at: ${_elevationMaxSweepDegree.toStringAsFixed(1)}°',
                                style: Theme.of(context).textTheme.bodyMedium
                                    ?.copyWith(
                                      color: Colors.green[700],
                                      fontWeight: FontWeight.bold,
                                    ),
                              ),
                              const SizedBox(height: 8),
                              Text(
                                'Current position: ${_elevationCurrentDegree.toStringAsFixed(1)}°',
                                style: Theme.of(context).textTheme.bodyMedium,
                              ),
                              const SizedBox(height: 12),
                              Container(
                                padding: const EdgeInsets.all(12),
                                decoration: BoxDecoration(
                                  color: Colors.orange[50],
                                  border: Border.all(
                                    color: Colors.orange[300]!,
                                  ),
                                  borderRadius: BorderRadius.circular(8),
                                ),
                                child: RichText(
                                  text: TextSpan(
                                    style: Theme.of(
                                      context,
                                    ).textTheme.bodyMedium,
                                    children: [
                                      TextSpan(
                                        text: _elevationDegreesToMaxRSL < 0
                                            ? 'Rotate DOWN '
                                            : 'Rotate UP ',
                                      ),
                                      TextSpan(
                                        text:
                                            '${_elevationDegreesToMaxRSL.abs().toStringAsFixed(1)}°',
                                        style: const TextStyle(
                                          fontWeight: FontWeight.bold,
                                          color: Colors.orange,
                                          fontSize: 18,
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
                              backgroundColor: Theme.of(
                                context,
                              ).colorScheme.primary,
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

          // This should display a real-time graph of signal strength over time
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
                  : 'Step 2: Elevation Alignment',
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                fontWeight: FontWeight.bold,
                color: Theme.of(context).colorScheme.primary,
              ),
            ),
            const SizedBox(height: 12),

            // Show only the relevant alignment card based on current step
            if (_currentStep == AlignmentStep.azimuth)
              _buildAlignmentCard(
                title: 'Azimuth',
                degreesLeft: _azimuthDegreesLeft,
                degreesRight: _azimuthDegreesRight,
                isActive: true,
                isConfirmed: _azimuthConfirmed,
              ),
            if (_currentStep == AlignmentStep.elevation)
              _buildAlignmentCard(
                title: 'Elevation',
                degreesLeft: _elevationDegreesDown,
                degreesRight: _elevationDegreesUp,
                isActive: true,
                isConfirmed: _elevationConfirmed,
              ),
          ],
        ),
      ),
    );
  }

  Widget _buildAlignmentCard({
    required String title,
    required double degreesLeft,
    required double degreesRight,
    required bool isActive,
    required bool isConfirmed,
  }) {
    return Container(
      decoration: BoxDecoration(
        color: isActive ? Colors.green[100] : Colors.white,
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
                    if (degreesLeft > 0)
                      TextSpan(
                        text: 'Rotate LEFT ${degreesLeft.toStringAsFixed(1)}°',
                        style: const TextStyle(
                          color: Colors.orange,
                          fontWeight: FontWeight.bold,
                        ),
                      )
                    else if (degreesRight > 0)
                      TextSpan(
                        text:
                            'Rotate RIGHT ${degreesRight.toStringAsFixed(1)}°',
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
                  backgroundColor: Colors.green[700],
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
      _elevationSweepData.clear();
      _elevationMaxSweepRSL = -100.0;
      _elevationDataLoaded = false;
      // Seed demo data when in debug mode
      if (_overrideMode) {
        _seedElevationDemoData();
      }
    });
  }

  void _completeSweep() {
    setState(() {
      _azimuthPhase = AzimuthPhase.sweepComplete;
    });
  }

  void _toggleAzimuthRecording() {
    setState(() {
      _isRecordingAzimuth = !_isRecordingAzimuth;
    });
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          _isRecordingAzimuth
              ? 'Recording started - rotate the antenna slowly'
              : 'Recording stopped',
        ),
        duration: const Duration(seconds: 2),
      ),
    );
  }

  void _toggleElevationRecording() {
    setState(() {
      _isRecordingElevation = !_isRecordingElevation;
    });
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          _isRecordingElevation
              ? 'Recording started - rotate the antenna slowly'
              : 'Recording stopped',
        ),
        duration: const Duration(seconds: 2),
      ),
    );
  }

  void _confirmAzimuthAlignment() {
    // Data should already be loaded from CSV
    if (_azimuthSweepData.isNotEmpty) {
      setState(() {
        _azimuthPhase = AzimuthPhase.aligned;
        _azimuthConfirmed = true;
        _currentStep = AlignmentStep.elevation;
        // Advance debug view if in override mode
        if (_overrideMode) {
          _overrideView = OverrideView.elevationSweep;
        }
      });

      _showConfirmationDialog(
        title: 'Azimuth Aligned',
        message:
            'Azimuth alignment complete. Target position: ${_azimuthMaxSweepDegree.toStringAsFixed(1)}°\n\nProceeding to elevation alignment...',
        onConfirm: () {
          Navigator.pop(context);
          // Start elevation sweep after azimuth is confirmed
          _startElevationSweep();
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
    // Data should already be loaded from CSV
    if (_elevationSweepData.isNotEmpty) {
      if (_currentSide == 1) {
        // Side 1 complete - proceed to side 2
        setState(() {
          _elevationPhase = ElevationPhase.aligned;
          _elevationConfirmed = true;
          _side1Complete = true;
          // Advance debug view to azimuth sweep for side 2 if in override mode
          if (_overrideMode) {
            _overrideView = OverrideView.azimuthSweep;
          }
        });

        _showSideCompleteDialog(
          title: 'Side 1 Alignment Complete',
          message:
              'Side 1 azimuth and elevation alignment is complete.\n\n'
              'Target elevation: ${_elevationMaxSweepDegree.toStringAsFixed(1)}° (rotate ${_elevationDegreesToMaxRSL.abs().toStringAsFixed(1)}° ${_elevationDegreesToMaxRSL < 0 ? "DOWN" : "UP"}).',
          disconnectMessage: 'Please DISCONNECT from Side 1 antenna now.',
          nextAction:
              'Connect to Side 2 antenna and tap "Continue" to proceed.',
          showStartNewAlignment: true,
          onConfirm: () {
            Navigator.pop(context);
            _startSide2();
          },
          onStartNew: () {
            Navigator.pop(context);
            _resetAlignment();
          },
        );
      } else {
        // Side 2 complete - all done
        setState(() {
          _elevationPhase = ElevationPhase.aligned;
          _elevationConfirmed = true;
          _processCompleted = true;
          _currentStep = AlignmentStep.finalized;
          // Advance debug view to completed if in override mode
          if (_overrideMode) {
            _overrideView = OverrideView.completed;
          }
        });

        _showSideCompleteDialog(
          title: 'Alignment Finalized',
          message:
              'Side 2 azimuth and elevation alignment is complete.\n\n'
              'Target elevation: ${_elevationMaxSweepDegree.toStringAsFixed(1)}° (rotate ${_elevationDegreesToMaxRSL.abs().toStringAsFixed(1)}° ${_elevationDegreesToMaxRSL < 0 ? "DOWN" : "UP"}).',
          disconnectMessage: 'Please DISCONNECT from Side 2 antenna now.',
          nextAction: 'Both antennas are now fully aligned!',
          showStartNewAlignment: false,
          onConfirm: () {
            Navigator.pop(context);
          },
        );
      }
    }
  }

  void _startSide2() {
    setState(() {
      _currentSide = 2;
      // Reset azimuth state for side 2
      _azimuthPhase = AzimuthPhase.sweepInProgress;
      _azimuthSweepData.clear();
      _azimuthMaxSweepRSL = -100.0;
      _azimuthMaxSweepDegree = 0.0;
      _azimuthDegreesToMaxRSL = 0.0;
      _azimuthConfirmed = false;
      _isRecordingAzimuth = false;
      _azimuthDataLoaded = false;
      // Reset elevation state for side 2
      _elevationPhase = ElevationPhase.waitingForStart;
      _elevationSweepData.clear();
      _elevationMaxSweepRSL = -100.0;
      _elevationMaxSweepDegree = 0.0;
      _elevationDegreesToMaxRSL = 0.0;
      _elevationConfirmed = false;
      _isRecordingElevation = false;
      _elevationDataLoaded = false;
      // Reset step
      _currentStep = AlignmentStep.azimuth;
      // Seed demo data when in debug mode
      if (_overrideMode) {
        _seedAzimuthDemoData();
      }
    });
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

  void _showSideCompleteDialog({
    required String title,
    required String message,
    required String disconnectMessage,
    required String nextAction,
    required VoidCallback onConfirm,
    bool showStartNewAlignment = false,
    VoidCallback? onStartNew,
  }) {
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (context) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: Row(
          children: [
            Icon(Icons.check_circle, color: Colors.green[600], size: 28),
            const SizedBox(width: 12),
            Expanded(child: Text(title)),
          ],
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(message),
            const SizedBox(height: 20),
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: Colors.orange[50],
                border: Border.all(color: Colors.orange[300]!),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Row(
                children: [
                  Icon(Icons.link_off, color: Colors.orange[700], size: 24),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      disconnectMessage,
                      style: TextStyle(
                        fontWeight: FontWeight.bold,
                        color: Colors.orange[900],
                        fontSize: 15,
                      ),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 16),
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: Colors.blue[50],
                border: Border.all(color: Colors.blue[300]!),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Row(
                children: [
                  Icon(Icons.arrow_forward, color: Colors.blue[700], size: 24),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      nextAction,
                      style: TextStyle(
                        fontWeight: FontWeight.w500,
                        color: Colors.blue[900],
                        fontSize: 14,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
        actions: [
          if (showStartNewAlignment && onStartNew != null)
            TextButton.icon(
              onPressed: onStartNew,
              icon: const Icon(Icons.refresh),
              label: const Text('Start New Alignment'),
              style: TextButton.styleFrom(foregroundColor: Colors.grey[700]),
            ),
          ElevatedButton.icon(
            onPressed: onConfirm,
            icon: const Icon(Icons.check),
            label: const Text('Continue'),
            style: ElevatedButton.styleFrom(
              backgroundColor: Colors.green[600],
              foregroundColor: Colors.white,
              padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
            ),
          ),
        ],
      ),
    );
  }

  void _resetAlignment() {
    setState(() {
      // Reset all state to start over
      _currentSide = 1;
      _side1Complete = false;
      _processCompleted = false;
      _currentStep = AlignmentStep.azimuth;

      // Reset azimuth state
      _azimuthPhase = AzimuthPhase.sweepInProgress;
      _azimuthSweepData.clear();
      _azimuthMaxSweepRSL = -100.0;
      _azimuthMaxSweepDegree = 0.0;
      _azimuthDegreesToMaxRSL = 0.0;
      _azimuthConfirmed = false;
      _isRecordingAzimuth = false;
      _azimuthDataLoaded = false;

      // Reset elevation state
      _elevationPhase = ElevationPhase.waitingForStart;
      _elevationSweepData.clear();
      _elevationMaxSweepRSL = -100.0;
      _elevationMaxSweepDegree = 0.0;
      _elevationDegreesToMaxRSL = 0.0;
      _elevationConfirmed = false;
      _isRecordingElevation = false;
      _elevationDataLoaded = false;

      // Reset override mode
      if (_overrideMode) {
        _overrideView = OverrideView.azimuthSweep;
        _seedAzimuthDemoData();
      }
    });
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
        Offset(
          (xLegend + legendDashWidth).clamp(legendX, legendX + 10),
          legendY + legendItemHeight,
        ),
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
      canvas,
      const Offset(legendX + 14, legendY + legendItemHeight - 6),
    );
  }

  @override
  bool shouldRepaint(SineWavePainter oldDelegate) {
    return oldDelegate.currentRSL != currentRSL || oldDelegate.maxRSL != maxRSL;
  }
}
