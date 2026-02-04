import 'dart:io';
import 'package:flutter/foundation.dart';

class VNAService {
  final String pythonPath;
  final String scriptPath;
  final String csvDir;
  final String ip;
  final String port;

  VNAService({
    this.pythonPath =
        '/home/sd2-group2/Documents/SD2_Codespace/Antenna_Aligner/.venv/bin/python',
    this.scriptPath =
        '/home/sd2-group2/Documents/SD2_Codespace/Antenna_Aligner/scripts/znle_pyvisa.py',
    this.csvDir =
        '/home/sd2-group2/Documents/SD2_Codespace/Antenna_Aligner/CSVs',
    this.ip = '192.168.15.92',
    this.port = '5025',
  });

  /// Get a single amplitude reading at the specified frequency
  Future<double?> getAmplitude({
    required double frequency,
    String param = 'S11',
    int points = 201,
  }) async {
    try {
      final timestamp = DateTime.now().millisecondsSinceEpoch;
      final outputFile = '$csvDir/temp_$timestamp.csv';

      // Run the Python script
      final result = await Process.run(
        pythonPath,
        [
          scriptPath,
          '--ip',
          ip,
          '--port',
          port,
          '--start',
          frequency.toString(),
          '--stop',
          frequency.toString(),
          '--points',
          '1',
          '--param',
          param,
          '--out',
          outputFile,
        ],
        environment: {'PLOTS_DIR': '$csvDir/../Plots'},
      );

      if (result.exitCode != 0) {
        debugPrint('Error running VNA script: ${result.stderr}');
        return null;
      }

      // Read the CSV file
      final file = File(outputFile);
      if (!await file.exists()) {
        debugPrint('Output file not found: $outputFile');
        return null;
      }

      final lines = await file.readAsLines();
      if (lines.length < 2) {
        debugPrint('CSV file has insufficient data');
        return null;
      }

      // Parse the amplitude (second column, second row)
      final dataLine = lines[1].split(',');
      if (dataLine.length < 2) {
        debugPrint('Invalid CSV format');
        return null;
      }

      final amplitude = double.tryParse(dataLine[1]);

      // Clean up temp file
      await file.delete();

      return amplitude;
    } catch (e) {
      debugPrint('Exception in getAmplitude: $e');
      return null;
    }
  }

  /// Get frequency sweep data
  Future<List<TracePoint>?> getFrequencySweep({
    required double startFreq,
    required double stopFreq,
    int points = 201,
    String param = 'S11',
  }) async {
    try {
      final timestamp = DateTime.now().millisecondsSinceEpoch;
      final outputFile = '$csvDir/sweep_$timestamp.csv';

      // Run the Python script
      final result = await Process.run(
        pythonPath,
        [
          scriptPath,
          '--ip',
          ip,
          '--port',
          port,
          '--start',
          startFreq.toString(),
          '--stop',
          stopFreq.toString(),
          '--points',
          points.toString(),
          '--param',
          param,
          '--out',
          outputFile,
        ],
        environment: {'PLOTS_DIR': '$csvDir/../Plots'},
      );

      if (result.exitCode != 0) {
        debugPrint('Error running VNA script: ${result.stderr}');
        return null;
      }

      // Read and parse the CSV file
      final file = File(outputFile);
      if (!await file.exists()) {
        debugPrint('Output file not found: $outputFile');
        return null;
      }

      final lines = await file.readAsLines();
      final tracePoints = <TracePoint>[];

      // Skip header row
      for (int i = 1; i < lines.length; i++) {
        final parts = lines[i].split(',');
        if (parts.length >= 2) {
          final freq = double.tryParse(parts[0]);
          final amp = double.tryParse(parts[1]);
          if (freq != null && amp != null) {
            tracePoints.add(TracePoint(frequency: freq, amplitude: amp));
          }
        }
      }

      // Clean up temp file
      await file.delete();

      return tracePoints.isEmpty ? null : tracePoints;
    } catch (e) {
      debugPrint('Exception in getFrequencySweep: $e');
      return null;
    }
  }

  /// Start monitor mode (continuous monitoring at a specific frequency)
  Stream<double> monitorFrequency({
    required double frequency,
    String param = 'S11',
    Duration interval = const Duration(seconds: 1),
  }) async* {
    while (true) {
      final amplitude = await getAmplitude(frequency: frequency, param: param);

      if (amplitude != null) {
        yield amplitude;
      }

      await Future.delayed(interval);
    }
  }
}

class TracePoint {
  final double frequency;
  final double amplitude;

  TracePoint({required this.frequency, required this.amplitude});

  @override
  String toString() => 'TracePoint(freq: ${frequency}Hz, amp: ${amplitude}dB)';
}
