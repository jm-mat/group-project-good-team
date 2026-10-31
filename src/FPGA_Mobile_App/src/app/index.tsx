import * as Device from 'expo-device';
import {
  Alert,
  Platform,
  Pressable,
  StyleSheet,
  Vibration,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { AnimatedIcon } from '@/components/animated-icon';
import { HintRow } from '@/components/hint-row';
import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { WebBadge } from '@/components/web-badge';
import { useEffect, useRef } from 'react';
import {
  BottomTabInset,
  MaxContentWidth,
  Spacing,
} from '@/constants/theme';

const FALL_SERVER_URL = 'http://192.168.1.72:50222';

export default function HomeScreen() {
  const wasFalling = useRef(false);

  // Poll the Node server for a fall event every second.
  useEffect(() => {
    const checkFallStatus = async () => {
      try {
        const response = await fetch(
          `${FALL_SERVER_URL}/status`
        );

        if (!response.ok) {
          throw new Error(
            `Server returned HTTP ${response.status}`
          );
        }

        const data = await response.json();

        if (data.isFalling && !wasFalling.current) {
          wasFalling.current = true;

          // Display the fall-warning message.
          Alert.alert(
            'Fall Warning',
            'The server reported that a fall may be occurring.'
          );

          // Vibrate the phone without requiring expo-notifications
          // or a custom development build.
          if (Platform.OS !== 'web') {
            Vibration.vibrate([
              0,    // Start immediately
              500,  // Vibrate for 500 ms
              200,  // Pause for 200 ms
              500,  // Vibrate again for 500 ms
            ]);
          }
        }

        // Reset the detection flag after the server clears the alert.
        // This allows a future fall event to trigger another warning.
        if (!data.isFalling) {
          wasFalling.current = false;
        }
      } catch (error) {
        console.log(
          'Could not connect to fall server:',
          error
        );
      }
    };

    // Check immediately when the screen loads.
    checkFallStatus();

    // Continue checking once per second.
    const timer = setInterval(
      checkFallStatus,
      1000
    );

    // Stop polling when the screen is removed.
    return () => {
      clearInterval(timer);
    };
  }, []);

  return (
    <ThemedView style={styles.container}>
      <SafeAreaView style={styles.safeArea}>
        <ThemedView style={styles.heroSection}>
          <AnimatedIcon />

          <ThemedText
            type="title"
            style={styles.title}
          >
            Choose a Notification Method
          </ThemedText>
        </ThemedView>

        {Platform.OS === 'web' && <WebBadge />}

        <Pressable
          onPress={() => {}}
          style={({ pressed }) => [
            styles.button,
            pressed && styles.buttonPressed,
          ]}
        >
          <ThemedText style={styles.buttonText}>
            Email
          </ThemedText>
        </Pressable>

        <Pressable
          onPress={() => {
            // Test the visible alert message.
            Alert.alert(
              'Fall Warning',
              'A possible fall was detected.'
            );

            // Test the phone vibration.
            if (Platform.OS !== 'web') {
              Vibration.vibrate([
                0,
                500,
                200,
                500,
              ]);
            }
          }}
          style={({ pressed }) => [
            styles.button,
            pressed && styles.buttonPressed,
          ]}
        >
          <ThemedText style={styles.buttonText}>
            Test Alert!
          </ThemedText>
        </Pressable>

        <Pressable
          onPress={() => {}}
          style={({ pressed }) => [
            styles.button,
            pressed && styles.buttonPressed,
          ]}
        >
          <ThemedText style={styles.buttonText}>
            App Notifications
          </ThemedText>
        </Pressable>
      </SafeAreaView>
    </ThemedView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    padding: 0,
    justifyContent: 'center',
    flexDirection: 'row',
    alignItems: 'center',
    gap: 14,
    transform: [{ translateY: 80 }],
  },

  safeArea: {
    flex: 1,
    paddingTop: 0,
    paddingHorizontal: Spacing.four,
    alignItems: 'center',
    gap: Spacing.three,
    paddingBottom: BottomTabInset + Spacing.three,
    maxWidth: MaxContentWidth,
  },

  heroSection: {
    alignItems: 'center',
    justifyContent: 'center',
    flex: 1,
    paddingHorizontal: Spacing.four,
    gap: Spacing.four,
  },

  title: {
    textAlign: 'center',
    fontSize: 45,
    letterSpacing: 1,
    color: 'white',
    marginTop: 20,
    marginBottom: 30,
  },

  stepContainer: {
    gap: Spacing.three,
    alignSelf: 'stretch',
    paddingHorizontal: Spacing.three,
    paddingVertical: Spacing.four,
    borderRadius: Spacing.four,
    marginBottom: 40,
  },

  button: {
    backgroundColor: '#0274DF',
    paddingVertical: 12,
    paddingHorizontal: 24,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: 'white',
    minWidth: 180,
    alignItems: 'center',
    marginTop: 0,
    marginBottom: 0,
  },

  buttonPressed: {
    opacity: 0.7,
    transform: [{ scale: 0.95 }],
  },

  buttonText: {
    color: 'white',
  },
});
