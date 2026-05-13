const byte alert_pin = 33;
const byte button_pin = 35;
volatile bool alert_state = LOW;
bool timer_state = LOW;
const byte listen_pin = 14;

void setup() {
  pinMode(alert_pin, OUTPUT);
  pinMode(button_pin, INPUT);
  pinMode(listen_pin, INPUT_PULLUP);
  pinMode(2, OUTPUT);
  attachInterrupt(digitalPinToInterrupt(button_pin), buttonPressed, FALLING);
  Serial.begin(9600);
}

// hardware interrupt on button press
void buttonPressed() {
  if (alert_state == HIGH) {
    alert_state = false;
    digitalWrite(alert_pin, LOW);
  }
}

// activate buzzer and led
void alert() {
  unsigned long start_time = millis();
  while (alert_state == true) {
    unsigned long elapsed_time = millis();
    if (elapsed_time - start_time >= 200) {
      start_time = elapsed_time;
      timer_state = !timer_state;
      digitalWrite(alert_pin, timer_state);
    }
  }
  digitalWrite(alert_pin, LOW);
  return;
}

// listen for input, alert when fall detected
void loop() {
  // detects on serial input, will change to wireless later
  if (Serial.available()) {
    char cmd = Serial.read();
    if (cmd == '1')  {
      alert_state = true;
    }
    if (cmd == '0') 
      alert_state = false;
  }
  if (alert_state == true)
    alert();
}
