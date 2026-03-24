import 'package:flutter/material.dart';
import 'dart:async' show TimeoutException;
import 'dart:convert';
import 'package:web_socket_channel/web_socket_channel.dart';

/// Data point from sweep containing degree position and amplitude
class SweepDataPoint {
  final double degree;
  final double amplitude; // amplitude in dBm

  SweepDataPoint({required this.degree, required this.amplitude});

  @override
  String toString() =>
      'SweepDataPoint(degree: $degree, amplitude: $amplitude dBm)';
}

void main() {
  runApp(const MyApp());
}

const kThemeNavy = Color(0xFF15324A);
const kThemeNavyDark = Color(0xFF0B1E2D);
const kThemeNavyLight = Color(0xFFE8EEF4);
const kThemeBurgundy = Color(0xFF7A1E3A);
const kThemeBurgundyDark = Color(0xFF5A132B);
const kThemeBurgundyLight = Color(0xFFF4E6EB);

enum AlignmentStep { azimuth, elevation, finalized }

enum AzimuthPhase {
  waitingForConnection,
  sweepInProgress,
  sweepComplete,
  aligned,
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
        colorScheme:
            ColorScheme.fromSeed(
              seedColor: kThemeNavy,
              brightness: Brightness.light,
            ).copyWith(
              primary: kThemeNavy,
              secondary: kThemeBurgundy,
              tertiary: kThemeBurgundy,
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
  WebSocketChannel? _channel;
  bool _isConnected = false;
  String _connectionStatus = 'Connecting to Raspberry Pi...';

  // Azimuth sweep data collection
  AzimuthPhase _azimuthPhase = AzimuthPhase.waitingForConnection;
  final List<SweepDataPoint> _azimuthSweepData =
      []; // Store all degree+amplitude readings during azimuth sweep
  double _azimuthMaxSweepRSL = -100.0; // Peak amplitude during azimuth sweep
  double _azimuthMaxSweepDegree = 0.0; // Degree position of peak amplitude
  double _azimuthCurrentDegree = 0.0; // Current azimuth degree position
  double _azimuthDegreesToMaxRSL =
      0.0; // Calculated: degrees to rotate to reach peak amplitude
  bool _isRecordingAzimuth = false; // Flag: continuously recording azimuth data

  // Elevation sweep data collection
  ElevationPhase _elevationPhase = ElevationPhase.waitingForStart;
  final List<SweepDataPoint> _elevationSweepData =
      []; // Store all degree+amplitude readings during elevation sweep
  double _elevationMaxSweepRSL =
      -100.0; // Peak amplitude during elevation sweep
  double _elevationMaxSweepDegree = 0.0; // Degree position of peak amplitude
  double _elevationCurrentDegree = 0.0; // Current elevation degree position
  double _elevationDegreesToMaxRSL =
      0.0; // Calculated: degrees to rotate to reach peak amplitude
  bool _isRecordingElevation =
      false; // Flag: continuously recording elevation data

  // Signal data from Raspberry Pi
  double _currentRSL = -85.5; // dBm
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

  bool _isConnecting = false;

  // Live-feed debug + gating controls
  bool _showDebugPanel = false;
  final bool _realVnaOnly = true;
  String _lastPacketSource = 'unknown';
  String _lastSweepType = '-';
  String _lastSweepStatus = '-';
  String _lastAmplitudeField = '-';
  double? _lastParsedAmplitude;
  bool _lastAmplitudeApplied = false;
  int _packetCounter = 0;
  String _lastPacketKeys = '-';
  DateTime? _lastPacketAt;

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
            final decoded = jsonDecode(message);
            if (decoded is! Map) {
              return;
            }
            final data = Map<String, dynamic>.from(decoded);
            setState(() {
              _applyIncomingPacket(data);
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

  /// Send command to Pi 5 to start a sweep
  void _sendStartSweep(String sweepType) {
    if (_isConnected && _channel != null) {
      _channel!.sink.add(
        jsonEncode({'cmd': 'START_SWEEP', 'sweep_type': sweepType}),
      );
      debugPrint('Sent START_SWEEP command for $sweepType');
    } else {
      debugPrint('Cannot send START_SWEEP - not connected');
    }
  }

  /// Send command to Pi 5 to stop the current sweep
  void _sendStopSweep() {
    if (_isConnected && _channel != null) {
      _channel!.sink.add(jsonEncode({'cmd': 'STOP_SWEEP'}));
      debugPrint('Sent STOP_SWEEP command');
    } else {
      debugPrint('Cannot send STOP_SWEEP - not connected');
    }
  }

  void _applyIncomingPacket(Map<String, dynamic> data) {
    _isConnected = true;

    final source =
        _extractString(data, ['source', 'data_source'])?.toLowerCase() ??
        'unknown';
    final isRealVnaPacket = source == 'vna';
    final allowAmplitudeFromPacket = !_realVnaOnly || isRealVnaPacket;

    _packetCounter += 1;
    _lastPacketSource = source;
    _lastPacketKeys = data.keys.join(', ');
    _lastPacketAt = DateTime.now();
    _connectionStatus = allowAmplitudeFromPacket
        ? 'Connected (real VNA feed)'
        : 'Connected - waiting for real VNA feed';

    final amplitudeEntry = _extractDoubleWithKey(data, [
      'rsl',
      'amplitude',
      'amplitude_db',
      'amplitude_dB',
      'signal',
      'signal_db',
      'level',
    ]);
    _lastAmplitudeField = amplitudeEntry?.key ?? '-';
    _lastParsedAmplitude = amplitudeEntry?.value;
    _lastAmplitudeApplied = false;

    // Keep initial flow behavior: sweep starts once link is live.
    if (_azimuthPhase == AzimuthPhase.waitingForConnection) {
      _azimuthPhase = AzimuthPhase.sweepInProgress;
      _azimuthSweepData.clear();
      _azimuthMaxSweepRSL = -100.0;
    }

    if (amplitudeEntry != null && allowAmplitudeFromPacket) {
      _currentRSL = amplitudeEntry.value;
      _lastAmplitudeApplied = true;
    }

    final azimuth = _extractDouble(data, [
      'azimuth_degree',
      'azimuth_deg',
      'azimuth',
      'current_azimuth',
      'az',
    ]);
    if (azimuth != null) {
      _azimuthCurrentDegree = azimuth;
    }

    final elevation = _extractDouble(data, [
      'elevation_degree',
      'elevation_deg',
      'elevation',
      'current_elevation',
      'el',
    ]);
    if (elevation != null) {
      _elevationCurrentDegree = elevation;
    }

    final sweepType = _extractString(data, [
      'sweep_type',
      'sweep_axis',
      'axis',
    ])?.toLowerCase();
    _lastSweepType = sweepType ?? '-';

    final sweepStatus = _extractString(data, ['sweep_status'])?.toLowerCase();
    _lastSweepStatus = sweepStatus ?? '-';

    final isSweepActive =
        data['sweep_active'] == true || data['sweep_status'] == 'started';

    if (isSweepActive && allowAmplitudeFromPacket) {
      final point = _extractSweepPoint(data['sweep_point'], sweepType);
      if (point != null) {
        _currentRSL = point.amplitude;
        _lastParsedAmplitude = point.amplitude;
        _lastAmplitudeField = 'sweep_point.amplitude';
        _lastAmplitudeApplied = true;
        _applyLiveSweepPoint(sweepType, point);
      }
    }

    if (sweepStatus == 'started') {
      if (sweepType == 'azimuth') {
        _azimuthPhase = AzimuthPhase.sweepInProgress;
        _azimuthSweepData.clear();
        _azimuthMaxSweepRSL = -100.0;
      } else if (sweepType == 'elevation') {
        _elevationPhase = ElevationPhase.sweepInProgress;
        _elevationSweepData.clear();
        _elevationMaxSweepRSL = -100.0;
      }
      debugPrint('Pi acknowledged $sweepType sweep start');
    }

    if (sweepStatus == 'completed') {
      _applyCompletedSweepData(
        sweepType,
        data['sweep_data'],
        allowAmplitude: allowAmplitudeFromPacket,
      );
    }

    // Fallback sampling mode if no structured sweep points are sent.
    if (allowAmplitudeFromPacket &&
        _isRecordingAzimuth &&
        _azimuthPhase == AzimuthPhase.sweepInProgress) {
      _azimuthSweepData.add(
        SweepDataPoint(degree: _azimuthCurrentDegree, amplitude: _currentRSL),
      );
      if (_currentRSL > _azimuthMaxSweepRSL) {
        _azimuthMaxSweepRSL = _currentRSL;
        _azimuthMaxSweepDegree = _azimuthCurrentDegree;
      }
    }

    if (allowAmplitudeFromPacket &&
        _isRecordingElevation &&
        _elevationPhase == ElevationPhase.sweepInProgress) {
      _elevationSweepData.add(
        SweepDataPoint(degree: _elevationCurrentDegree, amplitude: _currentRSL),
      );
      if (_currentRSL > _elevationMaxSweepRSL) {
        _elevationMaxSweepRSL = _currentRSL;
        _elevationMaxSweepDegree = _elevationCurrentDegree;
      }
    }

    final azLeft = _extractDouble(data, [
      'azimuth_degrees_left',
      'azimuth_turns_left',
    ]);
    if (azLeft != null) {
      _azimuthDegreesLeft = azLeft;
    }

    final azRight = _extractDouble(data, [
      'azimuth_degrees_right',
      'azimuth_turns_right',
    ]);
    if (azRight != null) {
      _azimuthDegreesRight = azRight;
    }

    final elUp = _extractDouble(data, [
      'elevation_degrees_up',
      'elevation_turns_up',
      'elevation_turns_left',
    ]);
    if (elUp != null) {
      _elevationDegreesUp = elUp;
    }

    final elDown = _extractDouble(data, [
      'elevation_degrees_down',
      'elevation_turns_down',
      'elevation_turns_right',
    ]);
    if (elDown != null) {
      _elevationDegreesDown = elDown;
    }
  }

  void _applyLiveSweepPoint(String? sweepType, SweepDataPoint point) {
    if (sweepType == 'azimuth') {
      if (_azimuthPhase != AzimuthPhase.sweepInProgress) {
        _azimuthPhase = AzimuthPhase.sweepInProgress;
        _azimuthSweepData.clear();
        _azimuthMaxSweepRSL = -100.0;
      }
      _azimuthCurrentDegree = point.degree;
      _azimuthSweepData.add(point);
      if (point.amplitude > _azimuthMaxSweepRSL) {
        _azimuthMaxSweepRSL = point.amplitude;
        _azimuthMaxSweepDegree = point.degree;
      }
      _calculateAzimuthDegreesToMax();
    } else if (sweepType == 'elevation') {
      if (_elevationPhase != ElevationPhase.sweepInProgress) {
        _elevationPhase = ElevationPhase.sweepInProgress;
        _elevationSweepData.clear();
        _elevationMaxSweepRSL = -100.0;
      }
      _elevationCurrentDegree = point.degree;
      _elevationSweepData.add(point);
      if (point.amplitude > _elevationMaxSweepRSL) {
        _elevationMaxSweepRSL = point.amplitude;
        _elevationMaxSweepDegree = point.degree;
      }
      _calculateElevationDegreesToMax();
    }
  }

  void _applyCompletedSweepData(
    String? sweepType,
    dynamic rawSweepData, {
    required bool allowAmplitude,
  }) {
    if (!allowAmplitude) {
      return;
    }

    final points = <SweepDataPoint>[];
    if (rawSweepData is List) {
      for (final raw in rawSweepData) {
        final parsedPoint = _extractSweepPoint(raw, sweepType);
        if (parsedPoint != null) {
          points.add(parsedPoint);
        }
      }
    }

    if (sweepType == 'azimuth') {
      if (points.isNotEmpty) {
        _azimuthSweepData
          ..clear()
          ..addAll(points);
        _currentRSL = points.last.amplitude;
        _azimuthMaxSweepRSL = -100.0;
        for (final point in points) {
          if (point.amplitude > _azimuthMaxSweepRSL) {
            _azimuthMaxSweepRSL = point.amplitude;
            _azimuthMaxSweepDegree = point.degree;
          }
        }
      }
      if (_azimuthSweepData.isNotEmpty) {
        _azimuthPhase = AzimuthPhase.sweepComplete;
        _calculateAzimuthDegreesToMax();
      }
    } else if (sweepType == 'elevation') {
      if (points.isNotEmpty) {
        _elevationSweepData
          ..clear()
          ..addAll(points);
        _currentRSL = points.last.amplitude;
        _elevationMaxSweepRSL = -100.0;
        for (final point in points) {
          if (point.amplitude > _elevationMaxSweepRSL) {
            _elevationMaxSweepRSL = point.amplitude;
            _elevationMaxSweepDegree = point.degree;
          }
        }
      }
      if (_elevationSweepData.isNotEmpty) {
        _elevationPhase = ElevationPhase.sweepComplete;
        _calculateElevationDegreesToMax();
      }
    }
  }

  SweepDataPoint? _extractSweepPoint(dynamic rawPoint, String? sweepType) {
    if (rawPoint is Map) {
      final point = Map<String, dynamic>.from(rawPoint);

      double? degree = _extractDouble(point, [
        'degree',
        'position',
        'x',
        'azimuth_degree',
        'azimuth_deg',
        'elevation_degree',
        'elevation_deg',
      ]);

      final amplitude = _extractDouble(point, [
        'amplitude',
        'rsl',
        'amplitude_db',
        'amplitude_dB',
        'signal',
        'value',
      ]);

      if (degree == null) {
        if (sweepType == 'azimuth') {
          degree = _azimuthCurrentDegree;
        } else if (sweepType == 'elevation') {
          degree = _elevationCurrentDegree;
        }
      }

      if (degree != null && amplitude != null) {
        return SweepDataPoint(degree: degree, amplitude: amplitude);
      }
      return null;
    }

    if (rawPoint is List && rawPoint.length >= 2) {
      final degree = _toDouble(rawPoint[0]);
      final amplitude = _toDouble(rawPoint[1]);
      if (degree != null && amplitude != null) {
        return SweepDataPoint(degree: degree, amplitude: amplitude);
      }
    }

    return null;
  }

  String? _extractString(Map<String, dynamic> data, List<String> keys) {
    for (final key in keys) {
      final value = data[key];
      if (value is String && value.trim().isNotEmpty) {
        return value.trim();
      }
    }
    return null;
  }

  double? _extractDouble(Map<String, dynamic> data, List<String> keys) {
    for (final key in keys) {
      final value = data[key];
      final parsed = _toDouble(value);
      if (parsed != null) {
        return parsed;
      }
    }
    return null;
  }

  MapEntry<String, double>? _extractDoubleWithKey(
    Map<String, dynamic> data,
    List<String> keys,
  ) {
    for (final key in keys) {
      final value = data[key];
      final parsed = _toDouble(value);
      if (parsed != null) {
        return MapEntry(key, parsed);
      }
    }
    return null;
  }

  double? _toDouble(dynamic value) {
    if (value is num) {
      return value.toDouble();
    }
    if (value is String) {
      final trimmed = value.trim();
      final direct = double.tryParse(trimmed);
      if (direct != null) {
        return direct;
      }

      // Accept values like "-23.4 dBm" or "amp=-23.4".
      final match = RegExp(r'-?\d+(?:\.\d+)?').firstMatch(trimmed);
      if (match != null) {
        return double.tryParse(match.group(0)!);
      }
    }
    return null;
  }

  void _toggleDebugPanel() {
    setState(() {
      _showDebugPanel = !_showDebugPanel;
    });
  }

  Widget _buildDebugToggleAction() {
    return IconButton(
      tooltip: _showDebugPanel
          ? 'Hide Live Feed Debug'
          : 'Show Live Feed Debug',
      icon: Icon(
        _showDebugPanel ? Icons.bug_report : Icons.bug_report_outlined,
      ),
      onPressed: _toggleDebugPanel,
    );
  }

  Widget _buildLiveFeedDebugPanel() {
    if (!_showDebugPanel) {
      return const SizedBox.shrink();
    }

    final timeText = _lastPacketAt == null
        ? 'never'
        : _lastPacketAt!.toIso8601String().substring(11, 19);

    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: kThemeNavyLight,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: kThemeNavy.withValues(alpha: 0.35)),
        ),
        child: DefaultTextStyle(
          style: Theme.of(
            context,
          ).textTheme.bodySmall!.copyWith(color: kThemeNavyDark, height: 1.3),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Live Feed Debug',
                style: Theme.of(context).textTheme.titleSmall?.copyWith(
                  color: kThemeNavyDark,
                  fontWeight: FontWeight.w700,
                ),
              ),
              const SizedBox(height: 6),
              Text(
                'realVnaOnly=$_realVnaOnly | source=$_lastPacketSource | packets=$_packetCounter | last=$timeText',
              ),
              Text(
                'ampField=$_lastAmplitudeField | parsed=${_lastParsedAmplitude?.toStringAsFixed(2) ?? '-'} | applied=$_lastAmplitudeApplied | current=${_currentRSL.toStringAsFixed(2)} dBm',
              ),
              Text('sweepType=$_lastSweepType | sweepStatus=$_lastSweepStatus'),
              Text(
                'keys=${_lastPacketKeys.length > 120 ? '${_lastPacketKeys.substring(0, 120)}...' : _lastPacketKeys}',
              ),
            ],
          ),
        ),
      ),
    );
  }

  /// Calculate degrees to rotate to reach peak amplitude for azimuth
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

  /// Calculate degrees to rotate to reach peak amplitude for elevation
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

  /// Best amplitude actually observed from sweep data — null until a sweep completes.
  double? get _bestSweepPeak {
    double best = -100.0;
    if (_azimuthMaxSweepRSL > -100.0) best = _azimuthMaxSweepRSL;
    if (_elevationMaxSweepRSL > best) best = _elevationMaxSweepRSL;
    return best > -100.0 ? best : null;
  }

  @override
  Widget build(BuildContext context) {
    // Show connection screen if not yet connected
    if (!_isConnected) {
      return _buildConnectionScreen();
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
      return _buildFinalizedScreen();
    }

    return Scaffold(
      appBar: AppBar(
        title: const Text('Microwave Signal Alignment'),
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
                      color: _isConnected ? kThemeBurgundy : Colors.red[300],
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
          _buildDebugToggleAction(),
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

                        _buildLiveFeedDebugPanel(),

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
    );
  }

  Widget _buildConnectionScreen() {
    return Scaffold(
      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [kThemeNavyDark, kThemeNavy, kThemeBurgundyDark],
            stops: [0.1, 0.55, 1.0],
          ),
        ),
        child: SafeArea(
          child: Center(
            child: Padding(
              padding: const EdgeInsets.all(24),
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 560),
                child: Container(
                  padding: const EdgeInsets.all(26),
                  decoration: BoxDecoration(
                    color: Colors.white.withValues(alpha: 0.12),
                    borderRadius: BorderRadius.circular(28),
                    border: Border.all(color: Colors.white24),
                    boxShadow: [
                      BoxShadow(
                        color: Colors.black.withValues(alpha: 0.18),
                        blurRadius: 28,
                        offset: const Offset(0, 12),
                      ),
                    ],
                  ),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Container(
                        width: 74,
                        height: 74,
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          color: Colors.white.withValues(alpha: 0.15),
                          border: Border.all(color: Colors.white30),
                        ),
                        child: const Icon(
                          Icons.radar_rounded,
                          color: Colors.white,
                          size: 36,
                        ),
                      ),
                      const SizedBox(height: 22),
                      Text(
                        'Connecting to Raspberry Pi',
                        style: Theme.of(context).textTheme.headlineSmall
                            ?.copyWith(
                              color: Colors.white,
                              fontWeight: FontWeight.w700,
                            ),
                        textAlign: TextAlign.center,
                      ),
                      const SizedBox(height: 10),
                      Text(
                        'Microwave Signal Alignment is waiting for live telemetry.',
                        style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                          color: Colors.white70,
                          height: 1.35,
                        ),
                        textAlign: TextAlign.center,
                      ),
                      const SizedBox(height: 22),
                      Container(
                        width: double.infinity,
                        padding: const EdgeInsets.symmetric(
                          horizontal: 16,
                          vertical: 14,
                        ),
                        decoration: BoxDecoration(
                          color: Colors.white.withValues(alpha: 0.1),
                          borderRadius: BorderRadius.circular(16),
                          border: Border.all(color: Colors.white24),
                        ),
                        child: Row(
                          children: [
                            const Icon(
                              Icons.router_rounded,
                              color: Colors.white,
                            ),
                            const SizedBox(width: 12),
                            Expanded(
                              child: Text(
                                'Endpoint: 192.168.15.192:8000',
                                style: Theme.of(context).textTheme.bodyMedium
                                    ?.copyWith(
                                      color: Colors.white,
                                      fontWeight: FontWeight.w600,
                                    ),
                              ),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(height: 20),
                      const CircularProgressIndicator(
                        valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
                        strokeWidth: 3,
                      ),
                      const SizedBox(height: 16),
                      Text(
                        _connectionStatus,
                        style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          color: Colors.white70,
                          fontStyle: FontStyle.italic,
                        ),
                        textAlign: TextAlign.center,
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildFinalizedScreen() {
    return Scaffold(
      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [kThemeNavyDark, kThemeNavy, kThemeBurgundy],
            stops: [0.0, 0.55, 1.0],
          ),
        ),
        child: SafeArea(
          child: Center(
            child: Padding(
              padding: const EdgeInsets.all(24),
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 620),
                child: Container(
                  padding: const EdgeInsets.all(28),
                  decoration: BoxDecoration(
                    color: Colors.white.withValues(alpha: 0.12),
                    borderRadius: BorderRadius.circular(30),
                    border: Border.all(color: Colors.white24),
                    boxShadow: [
                      BoxShadow(
                        color: Colors.black.withValues(alpha: 0.2),
                        blurRadius: 32,
                        offset: const Offset(0, 12),
                      ),
                    ],
                  ),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Container(
                        width: 88,
                        height: 88,
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          color: Colors.white.withValues(alpha: 0.15),
                          border: Border.all(color: Colors.white30),
                        ),
                        child: const Icon(
                          Icons.task_alt_rounded,
                          size: 46,
                          color: Colors.white,
                        ),
                      ),
                      const SizedBox(height: 22),
                      Text(
                        'Alignment Finalized',
                        style: Theme.of(context).textTheme.headlineMedium
                            ?.copyWith(
                              color: Colors.white,
                              fontWeight: FontWeight.w800,
                            ),
                        textAlign: TextAlign.center,
                      ),
                      const SizedBox(height: 10),
                      Text(
                        'Single-side antenna alignment has been completed successfully.',
                        style: Theme.of(context).textTheme.titleMedium
                            ?.copyWith(color: Colors.white70, height: 1.3),
                        textAlign: TextAlign.center,
                      ),
                      const SizedBox(height: 22),
                      Container(
                        width: double.infinity,
                        padding: const EdgeInsets.all(16),
                        decoration: BoxDecoration(
                          color: Colors.white.withValues(alpha: 0.1),
                          borderRadius: BorderRadius.circular(18),
                          border: Border.all(color: Colors.white24),
                        ),
                        child: Row(
                          children: [
                            const Icon(
                              Icons.link_off_rounded,
                              color: Colors.white,
                              size: 24,
                            ),
                            const SizedBox(width: 12),
                            Expanded(
                              child: Text(
                                'Disconnect from the antenna',
                                style: Theme.of(context).textTheme.titleSmall
                                    ?.copyWith(
                                      color: Colors.white,
                                      fontWeight: FontWeight.w700,
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
            ),
          ),
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
          actions: [_buildDebugToggleAction()],
        ),
        body: SafeArea(
          child: SingleChildScrollView(
            child: Center(
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 800),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Padding(
                      padding: const EdgeInsets.fromLTRB(16, 16, 16, 0),
                      child: SizedBox(
                        height: 320,
                        child: _buildIncomingSignalGraph(),
                      ),
                    ),
                    Padding(
                      padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
                      child: _buildLiveSweepGuidance(
                        axisName: 'Azimuth',
                        stepsTaken: _azimuthSweepData.length,
                        degreesToPeak: _azimuthDegreesToMaxRSL,
                        peakAmplitude: _azimuthMaxSweepRSL,
                        peakDegree: _azimuthMaxSweepDegree,
                      ),
                    ),
                    _buildLiveFeedDebugPanel(),
                    _buildVnaDataPanel(
                      title: 'Live Telemetry',
                      subtitle:
                          'Showing only the required incoming measurements for alignment.',
                      metrics: [
                        _buildVnaMetricTile(
                          icon: Icons.download_rounded,
                          label: 'Received Amplitude',
                          value:
                              '${(_azimuthSweepData.isNotEmpty ? _azimuthSweepData.last.amplitude : _currentRSL).toStringAsFixed(1)} dBm',
                          accentColor: kThemeNavy,
                          supportingText: 'Latest value from incoming data',
                        ),
                        _buildVnaMetricTile(
                          icon: Icons.settings_ethernet_rounded,
                          label: 'Motor Steps Taken',
                          value: '${_azimuthSweepData.length}',
                          accentColor: kThemeBurgundy,
                          supportingText: 'Step count from received samples',
                        ),
                        _buildVnaMetricTile(
                          icon: Icons.sensors_rounded,
                          label: 'Current Amplitude',
                          value: '${_currentRSL.toStringAsFixed(1)} dBm',
                          accentColor: Theme.of(context).colorScheme.primary,
                          supportingText: 'Live reading right now',
                        ),
                      ],
                      actions: [
                        ElevatedButton.icon(
                          onPressed: _completeSweep,
                          icon: const Icon(Icons.stop_circle_outlined),
                          label: const Text('Stop Sweep'),
                          style: ElevatedButton.styleFrom(
                            backgroundColor: kThemeBurgundy,
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
            ),
          ),
        ),
      );
    }

    if (_azimuthPhase == AzimuthPhase.sweepComplete) {
      return Scaffold(
        appBar: AppBar(
          title: const Text('Azimuth Alignment'),
          backgroundColor: Theme.of(context).colorScheme.primary,
          foregroundColor: Colors.white,
          actions: [_buildDebugToggleAction()],
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
                      _buildLiveFeedDebugPanel(),
                      _buildAlignmentPromptCard(
                        axisName: 'Azimuth',
                        targetDegree: _azimuthMaxSweepDegree,
                        degreesToMove: _azimuthDegreesToMaxRSL,
                        peakAmplitude: _azimuthMaxSweepRSL,
                        onConfirm: _confirmAzimuthAlignment,
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

    return const SizedBox.shrink();
  }

  Widget _buildElevationSweepScreen() {
    if (_elevationPhase == ElevationPhase.sweepInProgress) {
      return Scaffold(
        appBar: AppBar(
          title: const Text('Elevation Sweep'),
          backgroundColor: Theme.of(context).colorScheme.primary,
          foregroundColor: Colors.white,
          actions: [_buildDebugToggleAction()],
        ),
        body: SafeArea(
          child: SingleChildScrollView(
            child: Center(
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 800),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Padding(
                      padding: const EdgeInsets.fromLTRB(16, 16, 16, 0),
                      child: SizedBox(
                        height: 320,
                        child: _buildIncomingSignalGraph(),
                      ),
                    ),
                    Padding(
                      padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
                      child: _buildLiveSweepGuidance(
                        axisName: 'Elevation',
                        stepsTaken: _elevationSweepData.length,
                        degreesToPeak: _elevationDegreesToMaxRSL,
                        peakAmplitude: _elevationMaxSweepRSL,
                        peakDegree: _elevationMaxSweepDegree,
                        isVertical: true,
                      ),
                    ),
                    _buildLiveFeedDebugPanel(),
                    _buildVnaDataPanel(
                      title: 'Live Telemetry',
                      subtitle:
                          'Showing only the required incoming measurements for alignment.',
                      metrics: [
                        _buildVnaMetricTile(
                          icon: Icons.download_rounded,
                          label: 'Received Amplitude',
                          value:
                              '${(_elevationSweepData.isNotEmpty ? _elevationSweepData.last.amplitude : _currentRSL).toStringAsFixed(1)} dBm',
                          accentColor: kThemeNavy,
                          supportingText: 'Latest value from incoming data',
                        ),
                        _buildVnaMetricTile(
                          icon: Icons.settings_ethernet_rounded,
                          label: 'Motor Steps Taken',
                          value: '${_elevationSweepData.length}',
                          accentColor: kThemeBurgundy,
                          supportingText: 'Step count from received samples',
                        ),
                        _buildVnaMetricTile(
                          icon: Icons.sensors_rounded,
                          label: 'Current Amplitude',
                          value: '${_currentRSL.toStringAsFixed(1)} dBm',
                          accentColor: Theme.of(context).colorScheme.primary,
                          supportingText: 'Live reading right now',
                        ),
                      ],
                      actions: [
                        ElevatedButton.icon(
                          onPressed: _completeElevationSweep,
                          icon: const Icon(Icons.stop_circle_outlined),
                          label: const Text('Stop Sweep'),
                          style: ElevatedButton.styleFrom(
                            backgroundColor: kThemeBurgundy,
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
            ),
          ),
        ),
      );
    }

    if (_elevationPhase == ElevationPhase.sweepComplete) {
      return Scaffold(
        appBar: AppBar(
          title: const Text('Elevation Alignment'),
          backgroundColor: Theme.of(context).colorScheme.primary,
          foregroundColor: Colors.white,
          actions: [_buildDebugToggleAction()],
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
                      _buildLiveFeedDebugPanel(),
                      _buildAlignmentPromptCard(
                        axisName: 'Elevation',
                        targetDegree: _elevationMaxSweepDegree,
                        degreesToMove: _elevationDegreesToMaxRSL,
                        peakAmplitude: _elevationMaxSweepRSL,
                        onConfirm: _confirmElevationAlignment,
                        isVertical: true,
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

    return const SizedBox.shrink();
  }

  Widget _buildLiveSweepGuidance({
    required String axisName,
    required int stepsTaken,
    required double degreesToPeak,
    required double peakAmplitude,
    required double peakDegree,
    bool isVertical = false,
  }) {
    final hasPeak = stepsTaken > 1;
    final closeToPeak = degreesToPeak.abs() < 0.2;
    final direction = degreesToPeak < 0
        ? (isVertical ? 'DOWN' : 'LEFT')
        : (isVertical ? 'UP' : 'RIGHT');

    final message = !hasPeak
        ? 'Sweep the motor to search for the highest amplitude.'
        : closeToPeak
        ? 'Highest amplitude found. Stop sweep now; you are already at the peak position.'
        : 'Highest amplitude found. Stop sweep and go back $direction ${degreesToPeak.abs().toStringAsFixed(1)} deg.';

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: kThemeBurgundyLight,
        border: Border.all(color: kThemeBurgundy),
        borderRadius: BorderRadius.circular(14),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            '$axisName Sweep Guidance',
            style: Theme.of(context).textTheme.titleSmall?.copyWith(
              fontWeight: FontWeight.bold,
              color: kThemeBurgundyDark,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            message,
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
              color: kThemeBurgundyDark,
              height: 1.35,
            ),
          ),
          if (hasPeak) ...[
            const SizedBox(height: 8),
            Text(
              'Peak amplitude so far: ${peakAmplitude.toStringAsFixed(1)} dBm at ${peakDegree.toStringAsFixed(1)} deg',
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                color: Colors.black87,
                fontWeight: FontWeight.w600,
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildIncomingSignalGraph() {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(24),
        border: Border.all(color: kThemeNavy.withValues(alpha: 0.12)),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.06),
            blurRadius: 18,
            offset: const Offset(0, 8),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Incoming Signal Graph',
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
              fontWeight: FontWeight.w700,
              color: kThemeNavyDark,
            ),
          ),
          const SizedBox(height: 8),
          Expanded(
            child: CustomPaint(
              painter: AmplitudeLevelPainter(
                currentRSL: _currentRSL,
                peakRSL: _bestSweepPeak,
              ),
              size: Size.infinite,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildAlignmentPromptCard({
    required String axisName,
    required double targetDegree,
    required double degreesToMove,
    required double peakAmplitude,
    required VoidCallback onConfirm,
    bool isVertical = false,
  }) {
    final direction = degreesToMove < 0
        ? (isVertical ? 'DOWN' : 'LEFT')
        : (isVertical ? 'UP' : 'RIGHT');

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: kThemeBurgundyLight,
        border: Border.all(color: kThemeBurgundy),
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            '$axisName Alignment Prompt',
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
              color: kThemeBurgundyDark,
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 10),
          Text(
            'Move the stepper motor $direction ${degreesToMove.abs().toStringAsFixed(1)} deg to reach the peak amplitude.',
            style: Theme.of(context).textTheme.bodyLarge?.copyWith(
              color: kThemeBurgundyDark,
              height: 1.35,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            'Peak amplitude: ${peakAmplitude.toStringAsFixed(1)} dBm at ${targetDegree.toStringAsFixed(1)} deg',
            style: Theme.of(
              context,
            ).textTheme.bodyMedium?.copyWith(color: Colors.black87),
          ),
          const SizedBox(height: 16),
          SizedBox(
            width: double.infinity,
            child: ElevatedButton.icon(
              onPressed: onConfirm,
              icon: const Icon(Icons.done),
              label: const Text('Confirm Alignment'),
              style: ElevatedButton.styleFrom(
                backgroundColor: kThemeBurgundy,
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(vertical: 14),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSweepBanner({
    required IconData icon,
    required String title,
    required String message,
    required Color accentColor,
    required Color backgroundColor,
  }) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 0),
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.all(18),
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [backgroundColor, Colors.white],
          ),
          borderRadius: BorderRadius.circular(24),
          border: Border.all(color: accentColor.withValues(alpha: 0.18)),
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              width: 44,
              height: 44,
              decoration: BoxDecoration(
                color: accentColor.withValues(alpha: 0.12),
                borderRadius: BorderRadius.circular(14),
              ),
              child: Icon(icon, color: accentColor),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: Theme.of(context).textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.w700,
                      color: Colors.black87,
                    ),
                  ),
                  const SizedBox(height: 6),
                  Text(
                    message,
                    style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                      color: Colors.black54,
                      height: 1.35,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildVnaMetricTile({
    required IconData icon,
    required String label,
    required String value,
    required Color accentColor,
    String? supportingText,
  }) {
    return Container(
      constraints: const BoxConstraints(minWidth: 150, maxWidth: 220),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: accentColor.withValues(alpha: 0.12)),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.05),
            blurRadius: 18,
            offset: const Offset(0, 8),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 34,
            height: 34,
            decoration: BoxDecoration(
              color: accentColor.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Icon(icon, size: 18, color: accentColor),
          ),
          const SizedBox(height: 14),
          Text(
            label,
            style: Theme.of(context).textTheme.labelMedium?.copyWith(
              color: Colors.grey[600],
              letterSpacing: 0.2,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            value,
            style: Theme.of(context).textTheme.titleLarge?.copyWith(
              fontWeight: FontWeight.w800,
              color: Colors.black87,
            ),
          ),
          if (supportingText != null) ...[
            const SizedBox(height: 4),
            Text(
              supportingText,
              style: Theme.of(
                context,
              ).textTheme.bodySmall?.copyWith(color: Colors.grey[600]),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildVnaDataPanel({
    required String title,
    required String subtitle,
    required List<Widget> metrics,
    required List<Widget> actions,
  }) {
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.fromLTRB(16, 12, 16, 16),
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: const Color(0xFFF8F9FB),
        borderRadius: BorderRadius.circular(28),
        border: Border.all(color: kThemeNavy.withValues(alpha: 0.08)),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.05),
            blurRadius: 24,
            offset: const Offset(0, 10),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            title,
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
              fontWeight: FontWeight.w700,
              color: kThemeNavyDark,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            subtitle,
            style: Theme.of(
              context,
            ).textTheme.bodyMedium?.copyWith(color: Colors.grey[600]),
          ),
          const SizedBox(height: 18),
          Wrap(spacing: 14, runSpacing: 14, children: metrics),
          const SizedBox(height: 18),
          if (actions.isNotEmpty)
            Wrap(
              spacing: 12,
              runSpacing: 12,
              alignment: WrapAlignment.center,
              children: actions,
            ),
        ],
      ),
    );
  }

  Widget _buildSignalGraphSection() {
    return Container(
      padding: const EdgeInsets.fromLTRB(16, 14, 16, 10),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [Colors.white, kThemeNavyLight.withValues(alpha: 0.55)],
        ),
        borderRadius: BorderRadius.circular(28),
        border: Border.all(color: kThemeNavy.withValues(alpha: 0.08)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Live VNA Signal',
            style: Theme.of(context).textTheme.titleLarge?.copyWith(
              fontWeight: FontWeight.w800,
              color: kThemeNavyDark,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            'Track amplitude in real time while the antenna moves.',
            style: Theme.of(
              context,
            ).textTheme.bodyMedium?.copyWith(color: Colors.grey[600]),
          ),
          const SizedBox(height: 14),
          Wrap(
            spacing: 12,
            runSpacing: 12,
            children: [
              _buildVnaMetricTile(
                icon: Icons.graphic_eq_rounded,
                label: 'Current Amplitude',
                value: '${_currentRSL.toStringAsFixed(1)} dBm',
                accentColor: Theme.of(context).colorScheme.primary,
                supportingText: 'Live receiver reading',
              ),
              if (_bestSweepPeak != null)
                _buildVnaMetricTile(
                  icon: Icons.flag_rounded,
                  label: 'Best Sweep Peak',
                  value: '${_bestSweepPeak!.toStringAsFixed(1)} dBm',
                  accentColor: kThemeBurgundy,
                  supportingText: 'Highest amplitude from sweeps',
                ),
            ],
          ),
          const SizedBox(height: 14),
          Expanded(
            child: Container(
              decoration: BoxDecoration(
                color: Colors.white,
                border: Border.all(color: Colors.grey[300]!),
                borderRadius: BorderRadius.circular(24),
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withValues(alpha: 0.04),
                    blurRadius: 16,
                    offset: const Offset(0, 8),
                  ),
                ],
              ),
              padding: const EdgeInsets.all(16),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                crossAxisAlignment: CrossAxisAlignment.center,
                children: [
                  Expanded(
                    child: CustomPaint(
                      painter: AmplitudeLevelPainter(
                        currentRSL: _currentRSL,
                        peakRSL: _bestSweepPeak,
                      ),
                      size: Size.infinite,
                    ),
                  ),
                  const SizedBox(height: 10),
                  Text(
                    'Live amplitude level (dBm)',
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
        color: isActive ? kThemeBurgundyLight : Colors.white,
        border: Border.all(
          color: isConfirmed
              ? kThemeBurgundy
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
                style: Theme.of(
                  context,
                ).textTheme.titleSmall?.copyWith(fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 4),
              Text(
                isConfirmed ? 'Aligned' : 'In Progress',
                style: TextStyle(
                  color: isConfirmed ? kThemeBurgundy : Colors.orange[700],
                  fontWeight: FontWeight.w500,
                ),
              ),
            ],
          ),
          Row(
            children: [
              _buildDegreeIndicator(
                label: title == 'Azimuth' ? 'L' : 'D',
                value: degreesLeft,
                color: kThemeNavy,
              ),
              const SizedBox(width: 12),
              _buildDegreeIndicator(
                label: title == 'Azimuth' ? 'R' : 'U',
                value: degreesRight,
                color: kThemeBurgundy,
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildDegreeIndicator({
    required String label,
    required double value,
    required Color color,
  }) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color.withValues(alpha: 0.18)),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            label,
            style: TextStyle(color: color, fontWeight: FontWeight.w700),
          ),
          const SizedBox(height: 2),
          Text(
            value > 0 ? '${value.toStringAsFixed(1)} deg' : '--',
            style: const TextStyle(
              color: Colors.black87,
              fontWeight: FontWeight.w600,
            ),
          ),
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
                  backgroundColor: kThemeBurgundy,
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
    });
    _sendStartSweep('elevation');
  }

  /// Start azimuth sweep - called on connection or when manually restarting
  void _startAzimuthSweep() {
    setState(() {
      _azimuthPhase = AzimuthPhase.sweepInProgress;
      _azimuthSweepData.clear();
      _azimuthMaxSweepRSL = -100.0;
    });
    _sendStartSweep('azimuth');
  }

  void _completeSweep() {
    _sendStopSweep();
    setState(() {
      if (_azimuthSweepData.isEmpty) {
        _azimuthSweepData.add(
          SweepDataPoint(degree: _azimuthCurrentDegree, amplitude: _currentRSL),
        );
        _azimuthMaxSweepRSL = _currentRSL;
        _azimuthMaxSweepDegree = _azimuthCurrentDegree;
      }
      _calculateAzimuthDegreesToMax();
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
    // Alignment uses real-time sweep data
    if (_azimuthSweepData.isNotEmpty) {
      _calculateAzimuthDegreesToMax();
      setState(() {
        _azimuthPhase = AzimuthPhase.aligned;
        _azimuthConfirmed = true;
        _currentStep = AlignmentStep.elevation;
      });

      _showConfirmationDialog(
        title: 'Azimuth Aligned',
        message:
            'Azimuth alignment complete. Target position: ${_azimuthMaxSweepDegree.toStringAsFixed(1)} deg\n\nProceeding to elevation alignment...',
        onConfirm: () {
          Navigator.pop(context);
          // Start elevation sweep after azimuth is confirmed
          _startElevationSweep();
        },
      );
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            'No sweep data received yet. Continue sweeping, then press Stop Sweep.',
          ),
        ),
      );
    }
  }

  void _completeElevationSweep() {
    _sendStopSweep();
    setState(() {
      if (_elevationSweepData.isEmpty) {
        _elevationSweepData.add(
          SweepDataPoint(
            degree: _elevationCurrentDegree,
            amplitude: _currentRSL,
          ),
        );
        _elevationMaxSweepRSL = _currentRSL;
        _elevationMaxSweepDegree = _elevationCurrentDegree;
      }
      _calculateElevationDegreesToMax();
      _elevationPhase = ElevationPhase.sweepComplete;
    });
  }

  void _confirmElevationAlignment() {
    // Alignment uses real-time sweep data
    if (_elevationSweepData.isNotEmpty) {
      _calculateElevationDegreesToMax();
      setState(() {
        _elevationPhase = ElevationPhase.aligned;
        _elevationConfirmed = true;
        _processCompleted = true;
        _currentStep = AlignmentStep.finalized;
      });

      _showSideCompleteDialog(
        title: 'Alignment Finalized',
        message:
            'Azimuth and elevation alignment is complete.\n\n'
            'Target elevation: ${_elevationMaxSweepDegree.toStringAsFixed(1)} deg (rotate ${_elevationDegreesToMaxRSL.abs().toStringAsFixed(1)} deg ${_elevationDegreesToMaxRSL < 0 ? "DOWN" : "UP"}).',
        disconnectMessage: 'Please disconnect from the antenna now.',
        nextAction: 'Single-side alignment is complete.',
        showStartNewAlignment: true,
        onConfirm: () {
          Navigator.pop(context);
        },
        onStartNew: () {
          Navigator.pop(context);
          _resetAlignment();
        },
      );
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            'No sweep data received yet. Continue sweeping, then press Stop Sweep.',
          ),
        ),
      );
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
      // Reset elevation state for side 2
      _elevationPhase = ElevationPhase.waitingForStart;
      _elevationSweepData.clear();
      _elevationMaxSweepRSL = -100.0;
      _elevationMaxSweepDegree = 0.0;
      _elevationDegreesToMaxRSL = 0.0;
      _elevationConfirmed = false;
      _isRecordingElevation = false;
      // Reset step
      _currentStep = AlignmentStep.azimuth;
    });

    _sendStartSweep('azimuth');
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
            style: ElevatedButton.styleFrom(backgroundColor: kThemeBurgundy),
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
            const Icon(Icons.check_circle, color: kThemeBurgundy, size: 28),
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
                color: kThemeBurgundyLight,
                border: Border.all(color: kThemeBurgundy),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Row(
                children: [
                  const Icon(Icons.link_off, color: kThemeBurgundy, size: 24),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      disconnectMessage,
                      style: TextStyle(
                        fontWeight: FontWeight.bold,
                        color: kThemeBurgundyDark,
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
                color: kThemeNavyLight,
                border: Border.all(color: kThemeNavy),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Row(
                children: [
                  const Icon(Icons.arrow_forward, color: kThemeNavy, size: 24),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      nextAction,
                      style: TextStyle(
                        fontWeight: FontWeight.w500,
                        color: kThemeNavyDark,
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
              backgroundColor: kThemeBurgundy,
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

      // Reset elevation state
      _elevationPhase = ElevationPhase.waitingForStart;
      _elevationSweepData.clear();
      _elevationMaxSweepRSL = -100.0;
      _elevationMaxSweepDegree = 0.0;
      _elevationDegreesToMaxRSL = 0.0;
      _elevationConfirmed = false;
      _isRecordingElevation = false;
    });

    _sendStartSweep('azimuth');
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
                color: kThemeNavy,
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

class AmplitudeLevelPainter extends CustomPainter {
  final double currentRSL;
  final double? peakRSL;

  static const double _minDb = -120.0;
  static const double _maxDb = 0.0;

  AmplitudeLevelPainter({required this.currentRSL, this.peakRSL});

  @override
  void paint(Canvas canvas, Size size) {
    // Reserve bottom strip for dB labels
    const labelHeight = 14.0;
    final barHeight = size.height - labelHeight;

    // Background track
    canvas.drawRRect(
      RRect.fromRectAndRadius(
        Rect.fromLTWH(0, 0, size.width, barHeight),
        const Radius.circular(6),
      ),
      Paint()..color = Colors.grey[200]!,
    );

    // Filled bar — width proportional to current RSL
    final clamped = currentRSL.clamp(_minDb, _maxDb);
    final fraction = (clamped - _minDb) / (_maxDb - _minDb);
    final filledWidth = size.width * fraction;

    // Colour: red (weak signal) → yellow → green (strong signal)
    final barColor = HSVColor.lerp(
      const HSVColor.fromAHSV(1.0, 0, 0.85, 0.80),
      const HSVColor.fromAHSV(1.0, 120, 0.80, 0.70),
      fraction.clamp(0.0, 1.0),
    )!.toColor();

    if (filledWidth > 0) {
      canvas.drawRRect(
        RRect.fromRectAndRadius(
          Rect.fromLTWH(0, 0, filledWidth, barHeight),
          const Radius.circular(6),
        ),
        Paint()..color = barColor,
      );
    }

    // Grid lines at every 20 dB
    final gridPaint = Paint()
      ..color = Colors.white.withValues(alpha: 0.55)
      ..strokeWidth = 1;
    for (double db = -100; db <= -20; db += 20) {
      final x = (db - _minDb) / (_maxDb - _minDb) * size.width;
      canvas.drawLine(Offset(x, 0), Offset(x, barHeight), gridPaint);
    }

    // Sweep peak marker (burgundy vertical line)
    if (peakRSL != null) {
      final peakClamped = peakRSL!.clamp(_minDb, _maxDb);
      final peakX = (peakClamped - _minDb) / (_maxDb - _minDb) * size.width;
      canvas.drawLine(
        Offset(peakX, 0),
        Offset(peakX, barHeight),
        Paint()
          ..color = kThemeBurgundy
          ..strokeWidth = 2.5,
      );
    }

    // dB axis labels
    const labelStyle = TextStyle(
      color: Colors.black54,
      fontSize: 9,
      fontWeight: FontWeight.w400,
    );
    for (final db in const [-120.0, -80.0, -40.0, 0.0]) {
      final x = (db - _minDb) / (_maxDb - _minDb) * size.width;
      final tp = TextPainter(
        text: TextSpan(text: '${db.toInt()}', style: labelStyle),
        textDirection: TextDirection.ltr,
      )..layout();
      tp.paint(
        canvas,
        Offset(
          (x - tp.width / 2).clamp(0.0, size.width - tp.width),
          barHeight + 2,
        ),
      );
    }
  }

  @override
  bool shouldRepaint(AmplitudeLevelPainter old) =>
      old.currentRSL != currentRSL || old.peakRSL != peakRSL;
}
