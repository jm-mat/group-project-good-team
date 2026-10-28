import * as Device from 'expo-device';
import { Alert, Platform, Pressable, StyleSheet } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { AnimatedIcon } from '@/components/animated-icon';
import { HintRow } from '@/components/hint-row';
import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { WebBadge } from '@/components/web-badge';
import { BottomTabInset, MaxContentWidth, Spacing } from '@/constants/theme';

export default function HomeScreen() {
  return (
    <ThemedView style={styles.container}>
      <SafeAreaView style={styles.safeArea}>
        <ThemedView style={styles.heroSection}>
          <AnimatedIcon />
          <ThemedText type="title" style={styles.title}>
            Choose a Notification Method
          </ThemedText>
        </ThemedView>

        {Platform.OS === 'web' && <WebBadge />}
              <Pressable
                  onPress={() => { }}
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
                       Alert.alert(
                           'Fall Warning',
                           'A possible fall was detected.'
                       );
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
                  onPress={() => { }}
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
    transform: [{translateY: 80}],
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

