import 'package:app_web_1/core/config/theme_controller.dart';
import 'package:app_web_1/core/network/api_client.dart';
import 'package:app_web_1/core/state/workshop_controller.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  test('Una API caída y una preferencia antigua no sustituyen la base real', () async {
    SharedPreferences.setMockInitialValues({'motordesk_autonomous_mode': true});
    final api = ApiClient(client: MockClient((_) async {
      throw http.ClientException('Servidor no disponible');
    }));
    final theme = ThemeController(api);
    final workshop = WorkshopController(api, theme);
    await workshop.initialize();
    expect(workshop.isAutonomous, isFalse);
    await workshop.setAutonomousMode(true);
    expect(workshop.isAutonomous, isFalse);
    await expectLater(workshop.login('admin', 'incorrect-password'), throwsA(isA<ApiException>()));
    expect(workshop.signedIn, isFalse);
    workshop.dispose();
    theme.dispose();
  });
}
