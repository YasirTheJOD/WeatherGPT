// ignore: unused_import
import 'package:intl/intl.dart' as intl;

import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for Hindi (`hi`).
class AppLocalizationsHi extends AppLocalizations {
  AppLocalizationsHi([String locale = 'hi']) : super(locale);

  @override
  String get appTitle => 'WeatherGPT';

  @override
  String get appTagline => 'संवादात्मक मौसम खुफिया — SIH 2026 प्रोटोटाइप';

  @override
  String get navChat => 'चैट';

  @override
  String get navWeather => 'मौसम';

  @override
  String get navMap => 'नक्शा';

  @override
  String get navAlerts => 'चेतावनी';

  @override
  String get tabChat => 'चैट';

  @override
  String get tabWeather => 'मौसम';

  @override
  String get tabMap => 'नक्शा';

  @override
  String get weatherSearchHint => 'शहर खोजें…';

  @override
  String get useMyLocation => 'मेरी लोकेशन उपयोग करें';

  @override
  String get noPlacesFound => 'कोई जगह नहीं मिली।';

  @override
  String get searchFailed => 'खोज विफल रही। कृपया पुनः प्रयास करें।';

  @override
  String get locationUnavailable =>
      'आपकी लोकेशन प्राप्त नहीं हो सकी (अनुमति अस्वीकृत या अनुपलब्ध)।';

  @override
  String get weatherEmptyTitle => 'आप कहाँ देख रहे हैं?';

  @override
  String get weatherEmptyBody =>
      'लाइव स्थिति और 7-दिन का पूर्वानुमान देखने के लिए शहर खोजें या अपनी वर्तमान लोकेशन उपयोग करें।';

  @override
  String get quickPicks => 'कोशिश करें:';

  @override
  String get quickPickKolkata => 'कोलकाता';

  @override
  String get quickPickMumbai => 'मुंबई';

  @override
  String get quickPickDelhi => 'दिल्ली';

  @override
  String get quickPickBengaluru => 'बेंगलुरु';

  @override
  String get retry => 'पुनः प्रयास';

  @override
  String get humidity => 'आर्द्रता';

  @override
  String get wind => 'हवा';

  @override
  String get pressure => 'दाब';

  @override
  String get rainfall24h => 'वर्षा (24 घंटे)';

  @override
  String get observedAt => 'देखा गया';

  @override
  String get forecastHeader => '7-दिन का पूर्वानुमान';

  @override
  String get today => 'आज';

  @override
  String asOfTime(Object time) {
    return '$time तक';
  }

  @override
  String get officialSource => 'आधिकारिक स्रोत';

  @override
  String get sourceHeader => 'स्रोत';

  @override
  String get selectLocationForAlerts =>
      'उस क्षेत्र की आधिकारिक चेतावनी देखने के लिए कोई स्थान चुनें।';

  @override
  String get noAlertsNearby =>
      'इस स्थान के पास अभी कोई आधिकारिक चेतावनी नहीं है।';

  @override
  String get alertsHeader => 'आधिकारिक चेतावनी';

  @override
  String get officialWarning => 'आधिकारिक चेतावनी';

  @override
  String get whatToDo => 'क्या करें';

  @override
  String get affectedAreas => 'प्रभावित क्षेत्र';

  @override
  String issuedAt(Object time) {
    return 'जारी $time';
  }

  @override
  String expiresAt(Object time) {
    return 'समाप्त $time';
  }

  @override
  String get severityMinor => 'हल्का';

  @override
  String get severityModerate => 'मध्यम';

  @override
  String get severitySevere => 'गंभीर';

  @override
  String get severityExtreme => 'अत्यंत गंभीर';

  @override
  String get mapEmptyTitle => 'नक्शा देखें';

  @override
  String get mapEmptyBody =>
      'कोई स्थान चुनें — वह नक्शे पर पिन होगा, साथ में आधिकारिक चेतावनी क्षेत्र भी दिखेंगे।';

  @override
  String get mapAlertsFailed => 'चेतावनी क्षेत्र लोड नहीं हो सके।';

  @override
  String get chatHint => 'मौसम, पूर्वानुमान या चेतावनी पूछें…';

  @override
  String get chatWelcomeTitle => 'WeatherGPT से पूछें';

  @override
  String get chatWelcomeBody =>
      'अंग्रेज़ी या हिंग्लिश में पूछें — जवाब आधिकारिक मौसम डेटा पर आधारित होते हैं।';

  @override
  String get typing => 'WeatherGPT सोच रहा है…';

  @override
  String get send => 'भेजें';

  @override
  String get listening => 'सुन रहा है…';

  @override
  String get voiceUnsupported =>
      'वॉइस के लिए Chrome में वेब ऐप चाहिए — इसके बजाय अपना सवाल टाइप करें।';

  @override
  String get micTooltip => 'वॉइस इनपुट';

  @override
  String get stopListeningTooltip => 'सुनना बंद करें';

  @override
  String get language => 'भाषा';

  @override
  String get sourcesTitle => 'डेटा स्रोत';

  @override
  String get sourcesIntro =>
      'हर जवाब में बताया जाता है कि डेटा किसने दिया, कब लिया गया, और क्या यह आधिकारिक स्रोत है।';

  @override
  String get sourceOpenMeteo => 'लाइव मौसम अवलोकन और 7-दिन का पूर्वानुमान';

  @override
  String get sourceSachet => 'आधिकारिक सरकारी चेतावनी (CAP फ़ीड)';

  @override
  String get sourceBigDataCloud =>
      'आपकी वर्तमान लोकेशन के लिए रिवर्स जियोकोडिंग';

  @override
  String get sourceOpenStreetMap => 'नक्शे की टाइलें';

  @override
  String get sourcesLive => 'लाइव रजिस्ट्री';

  @override
  String sourcesSummary(Object available, Object total) {
    return '$total में से $available उपलब्ध';
  }

  @override
  String get sourcesFallbackNotice =>
      'अंतर्निहित सूची दिखाई जा रही है — लाइव रजिस्ट्री उपलब्ध नहीं है।';

  @override
  String get sourcesRegistryUnreachable => 'स्रोत रजिस्ट्री उपलब्ध नहीं है।';

  @override
  String get sourceAvailable => 'उपलब्ध';

  @override
  String get sourceUnavailable => 'अनुपलब्ध';

  @override
  String get sourceRequiresAuth => 'अनुमति आवश्यक';

  @override
  String get sourcePlanned => 'नियोजित';

  @override
  String get sourceImd => 'आधिकारिक अवलोकन, पूर्वानुमान और जिला चेतावनियाँ';

  @override
  String get sourceGeocoding => 'शहर खोज के लिए जियोकोडिंग';

  @override
  String get sourceLlm => 'डेटा को सरल भाषा में समझाता है';

  @override
  String get sourceMosdac => 'उपग्रह चित्र (भविष्य के लिए)';

  @override
  String get sourceGfs => 'भविष्य की मैप परतों के लिए कच्चा मॉडल आउटपुट';
}
