import 'package:flutter/material.dart';
import 'dart:math' show sin;

void main() {
  runApp(const MyApp());
}

enum AlignmentStep { azimuth, elevation, finalized }

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
  // TODO: Replace with actual data from LAN microwave signal source
  // This should fetch real RSL (Received Signal Level) data
  double _currentRSL = -85.5; // dBm
  final double _maxRSL = -75.0; // dBm
  int _azimuthTurnsLeft = 3;
  int _azimuthTurnsRight = 0;
  int _elevationTurnsLeft = 2;
  int _elevationTurnsRight = 0;

  AlignmentStep _currentStep = AlignmentStep.azimuth;
  bool _azimuthConfirmed = false;
  bool _elevationConfirmed = false;
  int _currentSide = 1; // Track which side we're aligning (1 or 2)
  bool _readyToFinalizeProcess =
      false; // true when side 2 is ready and user must press finalize
  bool _processCompleted = false; // true when the entire process is finalized

  void _updateRSLBasedOnAlignment() {
    // Calculate current RSL based on how aligned we are
    int totalTurnsNeeded = _currentStep == AlignmentStep.azimuth
        ? _azimuthTurnsLeft + _azimuthTurnsRight
        : _elevationTurnsLeft + _elevationTurnsRight;

    // If perfectly aligned (0 turns), signal should be at max RSL
    // If misaligned, signal degrades based on turns needed
    if (totalTurnsNeeded == 0) {
      _currentRSL = _maxRSL; // Perfect alignment
    } else {
      // Degrade signal by 2 dBm per turn needed
      _currentRSL = _maxRSL - (totalTurnsNeeded * 2.0);
    }

    // Ensure RSL doesn't go below our minimum
    if (_currentRSL < -100) _currentRSL = -100;
  }

  @override
  Widget build(BuildContext context) {
    // If user has completed the entire process, show final screen
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
                  'System aligned. Please disconned device from antenna.',
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
            // Turnbuckle Controls (for testing/simulation)
            if (_currentStep != AlignmentStep.finalized) ...[
              Text(
                'Test Controls: Adjust ${_currentStep == AlignmentStep.azimuth ? 'Azimuth' : 'Elevation'}',
                style: Theme.of(
                  context,
                ).textTheme.labelSmall?.copyWith(color: Colors.grey[600]),
              ),
              const SizedBox(height: 8),
              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  // Turn Left Button
                  FloatingActionButton.extended(
                    onPressed: _currentStep == AlignmentStep.azimuth
                        ? () => setState(() {
                              if (_azimuthTurnsLeft > 0) _azimuthTurnsLeft--;
                              _updateRSLBasedOnAlignment();
                            })
                        : () => setState(() {
                              if (_elevationTurnsLeft > 0) {
                                _elevationTurnsLeft--;
                              }
                              _updateRSLBasedOnAlignment();
                            }),
                    backgroundColor: Colors.orange[600],
                    icon: const Icon(Icons.rotate_left),
                    label: const Text('Left'),
                  ),
                  const SizedBox(width: 16),
                  // Turn Right Button
                  FloatingActionButton.extended(
                    onPressed: _currentStep == AlignmentStep.azimuth
                        ? () => setState(() {
                              if (_azimuthTurnsRight > 0) _azimuthTurnsRight--;
                              _updateRSLBasedOnAlignment();
                            })
                        : () => setState(() {
                              if (_elevationTurnsRight > 0) {
                                _elevationTurnsRight--;
                              }
                              _updateRSLBasedOnAlignment();
                            }),
                    backgroundColor: Colors.orange[600],
                    icon: const Icon(Icons.rotate_right),
                    label: const Text('Right'),
                  ),
                ],
              ),
              const SizedBox(height: 16),
            ],
            // Main confirmation/control buttons
            if (_currentStep != AlignmentStep.finalized)
              ElevatedButton.icon(
                onPressed: _currentStep == AlignmentStep.azimuth
                    ? _confirmAzimuth
                    : _confirmElevation,
                icon: const Icon(Icons.done),
                label: Text(
                  _currentStep == AlignmentStep.azimuth
                      ? 'Confirm Azimuth'
                      : 'Confirm Elevation',
                ),
                style: ElevatedButton.styleFrom(
                  backgroundColor: Theme.of(context).colorScheme.primary,
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
            if (_currentStep == AlignmentStep.elevation && _elevationConfirmed)
              ElevatedButton.icon(
                onPressed: _finalizeAlignment,
                icon: const Icon(Icons.flag),
                label: const Text('Finalize Alignment'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.green[600],
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
            if (_currentStep == AlignmentStep.finalized && _currentSide == 1)
              ElevatedButton.icon(
                onPressed: _goToOtherSide,
                icon: const Icon(Icons.arrow_forward),
                label: const Text('Go to Other Side'),
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
            if (_currentStep == AlignmentStep.finalized &&
                _currentSide == 2 &&
                _readyToFinalizeProcess)
              ElevatedButton.icon(
                onPressed: _finalizeProcess,
                icon: const Icon(Icons.done_all),
                label: const Text('Finalize Process'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.green[800],
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

  void _confirmAzimuth() {
    // Check if azimuth is aligned
    if (_azimuthTurnsLeft > 0 || _azimuthTurnsRight > 0) {
      _showAlignmentWarningDialog(
        title: 'Azimuth Not Aligned',
        message:
            'The azimuth appears to be misaligned. Please make the necessary adjustments before confirming.',
        onRetry: () => Navigator.pop(context),
      );
    } else {
      _showConfirmationDialog(
        title: 'Confirm Azimuth',
        message: 'Are you sure the azimuth is properly aligned?',
        onConfirm: () {
          setState(() {
            _azimuthConfirmed = true;
            _currentStep = AlignmentStep.elevation;
          });
          Navigator.pop(context);
        },
      );
    }
  }

  void _confirmElevation() {
    // Check if elevation is aligned
    if (_elevationTurnsLeft > 0 || _elevationTurnsRight > 0) {
      _showAlignmentWarningDialog(
        title: 'Elevation Not Aligned',
        message:
            'The elevation appears to be misaligned. Please make the necessary adjustments before confirming.',
        onRetry: () => Navigator.pop(context),
      );
    } else {
      _showConfirmationDialog(
        title: 'Confirm Elevation',
        message: 'Are you sure the elevation is properly aligned?',
        onConfirm: () {
          setState(() {
            _elevationConfirmed = true;
          });
          Navigator.pop(context);
        },
      );
    }
  }

  void _finalizeAlignment() {
    // Final check if both are aligned
    bool isProperlyAligned = (_azimuthTurnsLeft == 0 &&
        _azimuthTurnsRight == 0 &&
        _elevationTurnsLeft == 0 &&
        _elevationTurnsRight == 0);

    if (!isProperlyAligned) {
      _showAlignmentWarningDialog(
        title: 'Signal Not Fully Aligned',
        message:
            'The signal is still misaligned. Please return to azimuth or elevation adjustment to fine-tune the alignment.',
        onRetry: () {
          Navigator.pop(context);
          setState(() {
            _currentStep = AlignmentStep.azimuth;
          });
        },
      );
    } else {
      _showConfirmationDialog(
        title: 'Finalize Alignment',
        message:
            'Confirm that both azimuth and elevation are properly aligned and finalize this side?',
        onConfirm: () {
          setState(() {
            _currentStep = AlignmentStep.finalized;
            if (_currentSide == 2) {
              // For side 2, require an extra explicit finalize action
              _readyToFinalizeProcess = true;
            }
          });
          Navigator.pop(context);
        },
      );
    }
  }

  void _goToOtherSide() {
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (context) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: const Text('Go to Other Side'),
        content: const Text(
          'Please proceed to the other side of the installation and repeat the alignment process for the secondary link.',
        ),
        actions: [
          TextButton(
            onPressed: () {
              Navigator.pop(context);
              setState(() {
                // Reset for the other side
                _currentSide = 2;
                _currentStep = AlignmentStep.azimuth;
                _azimuthConfirmed = false;
                _elevationConfirmed = false;
                _azimuthTurnsLeft = 3;
                _azimuthTurnsRight = 0;
                _elevationTurnsLeft = 2;
                _elevationTurnsRight = 0;
                _currentRSL = -85.5; // Reset to initial misaligned value
                _readyToFinalizeProcess = false;
                _processCompleted = false;
              });
            },
            child: const Text('OK'),
          ),
        ],
      ),
    );
  }

  void _finalizeProcess() {
    // Finalize the entire process after side 2 confirmation
    setState(() {
      _processCompleted = true;
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

  void _showAlignmentWarningDialog({
    required String title,
    required String message,
    required VoidCallback onRetry,
  }) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: Row(
          children: [
            Icon(Icons.warning, color: Colors.orange[600]),
            const SizedBox(width: 8),
            Text(title),
          ],
        ),
        content: Text(message),
        actions: [
          ElevatedButton(
            onPressed: onRetry,
            style: ElevatedButton.styleFrom(
              backgroundColor: Colors.orange[600],
            ),
            child: const Text('Go Back and Adjust'),
          ),
        ],
      ),
    );
  }

  // Support helpline prompt: asks user for their number and shows placeholder instructions
  void _showSupportPrompt() {
    String userNumber = '';
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
        title: const Text('Support Helpline'),
        content: StatefulBuilder(
          builder: (context, setState) => Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Text(
                'Enter your phone number so support can call you back (optional):',
              ),
              const SizedBox(height: 8),
              TextField(
                keyboardType: TextInputType.phone,
                decoration: const InputDecoration(hintText: '+1 555 555 5555'),
                onChanged: (v) => userNumber = v.trim(),
              ),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () {
              Navigator.pop(context);
              final contact =
                  userNumber.isEmpty ? '+1-800-555-1234' : userNumber;
              _showSupportInstructions(contact);
            },
            child: const Text('Request Call'),
          ),
        ],
      ),
    );
  }

  // Placeholder instructions for contacting support
  void _showSupportInstructions(String userNumber) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
        title: const Text('Contacting Support'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('Support placeholder instructions:'),
            const SizedBox(height: 8),
            const Text('Call: +1-800-555-1234'),
            const SizedBox(height: 6),
            Text('When prompted, provide this callback number: $userNumber'),
            const SizedBox(height: 6),
            const Text('Reference: Provide link ID and signal readings.'),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('OK'),
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
      ..color = const Color(0xFF0D47A1).withOpacity(0.1)
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

    // Draw center line (0 dBm reference)
    final centerY = size.height / 2;
    canvas.drawLine(
      Offset(0, centerY),
      Offset(size.width, centerY),
      Paint()
        ..color = Colors.grey[400]!
        ..strokeWidth = 1,
    );

    // Create sine wave path
    final path = Path();
    final amplitude = size.height * 0.35;
    const frequency = 0.02;

    for (double x = 0; x < size.width; x++) {
      // Add variation to simulate signal strength changes
      final baseWave = amplitude * sin(x * frequency);
      // Modulate amplitude based on current RSL (closer to max = higher amplitude)
      final rslFactor = ((maxRSL - currentRSL) / (maxRSL - (-100))) * 0.5 + 0.5;
      final y = centerY - (baseWave * rslFactor);

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

    // Draw the sine wave line
    canvas.drawPath(path, paint);

    // Draw current signal level marker
    final currentX = size.width * 0.85;
    final currentY = centerY - (amplitude * sin(currentX * frequency) * 0.5);

    canvas.drawCircle(
      Offset(currentX, currentY),
      6,
      Paint()..color = Colors.red[600]!,
    );
    canvas.drawCircle(
      Offset(currentX, currentY),
      8,
      Paint()
        ..color = Colors.red[600]!
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2,
    );
  }

  @override
  bool shouldRepaint(SineWavePainter oldDelegate) {
    return oldDelegate.currentRSL != currentRSL || oldDelegate.maxRSL != maxRSL;
  }
}
