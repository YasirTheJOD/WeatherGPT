import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:intl/intl.dart' as intl;

import 'app_localizations_en.dart';
import 'app_localizations_hi.dart';

// ignore_for_file: type=lint

/// Callers can lookup localized strings with an instance of AppLocalizations
/// returned by `AppLocalizations.of(context)`.
///
/// Applications need to include `AppLocalizations.delegate()` in their app's
/// `localizationDelegates` list, and the locales they support in the app's
/// `supportedLocales` list. For example:
///
/// ```dart
/// import 'l10n/app_localizations.dart';
///
/// return MaterialApp(
///   localizationsDelegates: AppLocalizations.localizationsDelegates,
///   supportedLocales: AppLocalizations.supportedLocales,
///   home: MyApplicationHome(),
/// );
/// ```
///
/// ## Update pubspec.yaml
///
/// Please make sure to update your pubspec.yaml to include the following
/// packages:
///
/// ```yaml
/// dependencies:
///   # Internationalization support.
///   flutter_localizations:
///     sdk: flutter
///   intl: any # Use the pinned version from flutter_localizations
///
///   # Rest of dependencies
/// ```
///
/// ## iOS Applications
///
/// iOS applications define key application metadata, including supported
/// locales, in an Info.plist file that is built into the application bundle.
/// To configure the locales supported by your app, you’ll need to edit this
/// file.
///
/// First, open your project’s ios/Runner.xcworkspace Xcode workspace file.
/// Then, in the Project Navigator, open the Info.plist file under the Runner
/// project’s Runner folder.
///
/// Next, select the Information Property List item, select Add Item from the
/// Editor menu, then select Localizations from the pop-up menu.
///
/// Select and expand the newly-created Localizations item then, for each
/// locale your application supports, add a new item and select the locale
/// you wish to add from the pop-up menu in the Value field. This list should
/// be consistent with the languages listed in the AppLocalizations.supportedLocales
/// property.
abstract class AppLocalizations {
  AppLocalizations(String locale)
    : localeName = intl.Intl.canonicalizedLocale(locale.toString());

  final String localeName;

  static AppLocalizations of(BuildContext context) {
    return Localizations.of<AppLocalizations>(context, AppLocalizations)!;
  }

  static const LocalizationsDelegate<AppLocalizations> delegate =
      _AppLocalizationsDelegate();

  /// A list of this localizations delegate along with the default localizations
  /// delegates.
  ///
  /// Returns a list of localizations delegates containing this delegate along with
  /// GlobalMaterialLocalizations.delegate, GlobalCupertinoLocalizations.delegate,
  /// and GlobalWidgetsLocalizations.delegate.
  ///
  /// Additional delegates can be added by appending to this list in
  /// MaterialApp. This list does not have to be used at all if a custom list
  /// of delegates is preferred or required.
  static const List<LocalizationsDelegate<dynamic>> localizationsDelegates =
      <LocalizationsDelegate<dynamic>>[
        delegate,
        GlobalMaterialLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
      ];

  /// A list of this localizations delegate's supported locales.
  static const List<Locale> supportedLocales = <Locale>[
    Locale('en'),
    Locale('hi'),
  ];

  /// No description provided for @appTitle.
  ///
  /// In en, this message translates to:
  /// **'WeatherGPT'**
  String get appTitle;

  /// No description provided for @appTagline.
  ///
  /// In en, this message translates to:
  /// **'Conversational weather intelligence — SIH 2026 prototype'**
  String get appTagline;

  /// No description provided for @navChat.
  ///
  /// In en, this message translates to:
  /// **'Chat'**
  String get navChat;

  /// No description provided for @navWeather.
  ///
  /// In en, this message translates to:
  /// **'Weather'**
  String get navWeather;

  /// No description provided for @navMap.
  ///
  /// In en, this message translates to:
  /// **'Map'**
  String get navMap;

  /// No description provided for @navAlerts.
  ///
  /// In en, this message translates to:
  /// **'Alerts'**
  String get navAlerts;

  /// No description provided for @tabChat.
  ///
  /// In en, this message translates to:
  /// **'Chat'**
  String get tabChat;

  /// No description provided for @tabWeather.
  ///
  /// In en, this message translates to:
  /// **'Weather'**
  String get tabWeather;

  /// No description provided for @tabMap.
  ///
  /// In en, this message translates to:
  /// **'Map'**
  String get tabMap;

  /// No description provided for @weatherSearchHint.
  ///
  /// In en, this message translates to:
  /// **'Search for a city…'**
  String get weatherSearchHint;

  /// No description provided for @useMyLocation.
  ///
  /// In en, this message translates to:
  /// **'Use my location'**
  String get useMyLocation;

  /// No description provided for @noPlacesFound.
  ///
  /// In en, this message translates to:
  /// **'No places found.'**
  String get noPlacesFound;

  /// No description provided for @searchFailed.
  ///
  /// In en, this message translates to:
  /// **'Search failed. Please try again.'**
  String get searchFailed;

  /// No description provided for @locationUnavailable.
  ///
  /// In en, this message translates to:
  /// **'Could not get your location (permission denied or unavailable).'**
  String get locationUnavailable;

  /// No description provided for @weatherEmptyTitle.
  ///
  /// In en, this message translates to:
  /// **'Where are you looking?'**
  String get weatherEmptyTitle;

  /// No description provided for @weatherEmptyBody.
  ///
  /// In en, this message translates to:
  /// **'Search for a city or use your current location to see live conditions and the 7-day forecast.'**
  String get weatherEmptyBody;

  /// No description provided for @quickPicks.
  ///
  /// In en, this message translates to:
  /// **'Try:'**
  String get quickPicks;

  /// No description provided for @quickPickKolkata.
  ///
  /// In en, this message translates to:
  /// **'Kolkata'**
  String get quickPickKolkata;

  /// No description provided for @quickPickMumbai.
  ///
  /// In en, this message translates to:
  /// **'Mumbai'**
  String get quickPickMumbai;

  /// No description provided for @quickPickDelhi.
  ///
  /// In en, this message translates to:
  /// **'Delhi'**
  String get quickPickDelhi;

  /// No description provided for @quickPickBengaluru.
  ///
  /// In en, this message translates to:
  /// **'Bengaluru'**
  String get quickPickBengaluru;

  /// No description provided for @retry.
  ///
  /// In en, this message translates to:
  /// **'Retry'**
  String get retry;

  /// No description provided for @humidity.
  ///
  /// In en, this message translates to:
  /// **'Humidity'**
  String get humidity;

  /// No description provided for @wind.
  ///
  /// In en, this message translates to:
  /// **'Wind'**
  String get wind;

  /// No description provided for @pressure.
  ///
  /// In en, this message translates to:
  /// **'Pressure'**
  String get pressure;

  /// No description provided for @rainfall24h.
  ///
  /// In en, this message translates to:
  /// **'Rain (24h)'**
  String get rainfall24h;

  /// No description provided for @rainfallNext24h.
  ///
  /// In en, this message translates to:
  /// **'Rain (next 24h)'**
  String get rainfallNext24h;

  /// No description provided for @rainfallNow.
  ///
  /// In en, this message translates to:
  /// **'Rain (now)'**
  String get rainfallNow;

  /// No description provided for @rainfallGeneric.
  ///
  /// In en, this message translates to:
  /// **'Rain'**
  String get rainfallGeneric;

  /// No description provided for @observedAt.
  ///
  /// In en, this message translates to:
  /// **'Observed at'**
  String get observedAt;

  /// No description provided for @forecastHeader.
  ///
  /// In en, this message translates to:
  /// **'7-day forecast'**
  String get forecastHeader;

  /// No description provided for @today.
  ///
  /// In en, this message translates to:
  /// **'Today'**
  String get today;

  /// No description provided for @asOfTime.
  ///
  /// In en, this message translates to:
  /// **'As of {time}'**
  String asOfTime(Object time);

  /// No description provided for @officialSource.
  ///
  /// In en, this message translates to:
  /// **'Official source'**
  String get officialSource;

  /// No description provided for @sourceHeader.
  ///
  /// In en, this message translates to:
  /// **'Source'**
  String get sourceHeader;

  /// No description provided for @selectLocationForAlerts.
  ///
  /// In en, this message translates to:
  /// **'Select a location to see official warnings for that area.'**
  String get selectLocationForAlerts;

  /// No description provided for @noAlertsNearby.
  ///
  /// In en, this message translates to:
  /// **'No official warnings near this location right now.'**
  String get noAlertsNearby;

  /// No description provided for @alertsHeader.
  ///
  /// In en, this message translates to:
  /// **'Official warnings'**
  String get alertsHeader;

  /// No description provided for @officialWarning.
  ///
  /// In en, this message translates to:
  /// **'OFFICIAL WARNING'**
  String get officialWarning;

  /// No description provided for @whatToDo.
  ///
  /// In en, this message translates to:
  /// **'What to do'**
  String get whatToDo;

  /// No description provided for @affectedAreas.
  ///
  /// In en, this message translates to:
  /// **'Affected areas'**
  String get affectedAreas;

  /// No description provided for @issuedAt.
  ///
  /// In en, this message translates to:
  /// **'Issued {time}'**
  String issuedAt(Object time);

  /// No description provided for @expiresAt.
  ///
  /// In en, this message translates to:
  /// **'Expires {time}'**
  String expiresAt(Object time);

  /// No description provided for @severityMinor.
  ///
  /// In en, this message translates to:
  /// **'Minor'**
  String get severityMinor;

  /// No description provided for @severityModerate.
  ///
  /// In en, this message translates to:
  /// **'Moderate'**
  String get severityModerate;

  /// No description provided for @severitySevere.
  ///
  /// In en, this message translates to:
  /// **'Severe'**
  String get severitySevere;

  /// No description provided for @severityExtreme.
  ///
  /// In en, this message translates to:
  /// **'Extreme'**
  String get severityExtreme;

  /// No description provided for @mapEmptyTitle.
  ///
  /// In en, this message translates to:
  /// **'Explore the map'**
  String get mapEmptyTitle;

  /// No description provided for @mapEmptyBody.
  ///
  /// In en, this message translates to:
  /// **'Pick a location to see it pinned on the map, along with any official warning areas.'**
  String get mapEmptyBody;

  /// No description provided for @mapAlertsFailed.
  ///
  /// In en, this message translates to:
  /// **'Couldn\'t load alert areas.'**
  String get mapAlertsFailed;

  /// No description provided for @chatHint.
  ///
  /// In en, this message translates to:
  /// **'Ask about weather, forecasts or alerts…'**
  String get chatHint;

  /// No description provided for @chatWelcomeTitle.
  ///
  /// In en, this message translates to:
  /// **'Ask WeatherGPT'**
  String get chatWelcomeTitle;

  /// No description provided for @chatWelcomeBody.
  ///
  /// In en, this message translates to:
  /// **'Ask in English or Hinglish — answers are grounded in official weather data.'**
  String get chatWelcomeBody;

  /// No description provided for @typing.
  ///
  /// In en, this message translates to:
  /// **'WeatherGPT is thinking…'**
  String get typing;

  /// No description provided for @send.
  ///
  /// In en, this message translates to:
  /// **'Send'**
  String get send;

  /// No description provided for @listening.
  ///
  /// In en, this message translates to:
  /// **'Listening…'**
  String get listening;

  /// No description provided for @voiceUnsupported.
  ///
  /// In en, this message translates to:
  /// **'Voice needs the web app in Chrome — type your question instead.'**
  String get voiceUnsupported;

  /// No description provided for @micTooltip.
  ///
  /// In en, this message translates to:
  /// **'Voice input'**
  String get micTooltip;

  /// No description provided for @stopListeningTooltip.
  ///
  /// In en, this message translates to:
  /// **'Stop listening'**
  String get stopListeningTooltip;

  /// No description provided for @language.
  ///
  /// In en, this message translates to:
  /// **'Language'**
  String get language;

  /// No description provided for @sourcesTitle.
  ///
  /// In en, this message translates to:
  /// **'Data sources'**
  String get sourcesTitle;

  /// No description provided for @sourcesIntro.
  ///
  /// In en, this message translates to:
  /// **'Every answer shows who provided the data, when it was fetched, and whether it is an official source.'**
  String get sourcesIntro;

  /// No description provided for @sourceOpenMeteo.
  ///
  /// In en, this message translates to:
  /// **'Live observations & 7-day forecast'**
  String get sourceOpenMeteo;

  /// No description provided for @sourceSachet.
  ///
  /// In en, this message translates to:
  /// **'Official government warnings (CAP feed)'**
  String get sourceSachet;

  /// No description provided for @sourceBigDataCloud.
  ///
  /// In en, this message translates to:
  /// **'Reverse geocoding for your current location'**
  String get sourceBigDataCloud;

  /// No description provided for @sourceOpenStreetMap.
  ///
  /// In en, this message translates to:
  /// **'Map tiles'**
  String get sourceOpenStreetMap;

  /// No description provided for @sourcesLive.
  ///
  /// In en, this message translates to:
  /// **'Live registry'**
  String get sourcesLive;

  /// No description provided for @sourcesSummary.
  ///
  /// In en, this message translates to:
  /// **'{available} of {total} available'**
  String sourcesSummary(Object available, Object total);

  /// No description provided for @sourcesFallbackNotice.
  ///
  /// In en, this message translates to:
  /// **'Showing the built-in list — the live registry is unreachable.'**
  String get sourcesFallbackNotice;

  /// No description provided for @sourcesRegistryUnreachable.
  ///
  /// In en, this message translates to:
  /// **'Source registry unreachable.'**
  String get sourcesRegistryUnreachable;

  /// No description provided for @sourceAvailable.
  ///
  /// In en, this message translates to:
  /// **'Available'**
  String get sourceAvailable;

  /// No description provided for @sourceUnavailable.
  ///
  /// In en, this message translates to:
  /// **'Unavailable'**
  String get sourceUnavailable;

  /// No description provided for @sourceRequiresAuth.
  ///
  /// In en, this message translates to:
  /// **'Requires authorization'**
  String get sourceRequiresAuth;

  /// No description provided for @sourcePlanned.
  ///
  /// In en, this message translates to:
  /// **'Planned'**
  String get sourcePlanned;

  /// No description provided for @sourceImd.
  ///
  /// In en, this message translates to:
  /// **'Official observations, forecasts and district warnings'**
  String get sourceImd;

  /// No description provided for @sourceGeocoding.
  ///
  /// In en, this message translates to:
  /// **'Geocoding for city search'**
  String get sourceGeocoding;

  /// No description provided for @sourceLlm.
  ///
  /// In en, this message translates to:
  /// **'Explains the data in plain language'**
  String get sourceLlm;

  /// No description provided for @sourceMosdac.
  ///
  /// In en, this message translates to:
  /// **'Satellite imagery (future scope)'**
  String get sourceMosdac;

  /// No description provided for @sourceGfs.
  ///
  /// In en, this message translates to:
  /// **'Raw model output for future map layers'**
  String get sourceGfs;
}

class _AppLocalizationsDelegate
    extends LocalizationsDelegate<AppLocalizations> {
  const _AppLocalizationsDelegate();

  @override
  Future<AppLocalizations> load(Locale locale) {
    return SynchronousFuture<AppLocalizations>(lookupAppLocalizations(locale));
  }

  @override
  bool isSupported(Locale locale) =>
      <String>['en', 'hi'].contains(locale.languageCode);

  @override
  bool shouldReload(_AppLocalizationsDelegate old) => false;
}

AppLocalizations lookupAppLocalizations(Locale locale) {
  // Lookup logic when only language code is specified.
  switch (locale.languageCode) {
    case 'en':
      return AppLocalizationsEn();
    case 'hi':
      return AppLocalizationsHi();
  }

  throw FlutterError(
    'AppLocalizations.delegate failed to load unsupported locale "$locale". This is likely '
    'an issue with the localizations generation tool. Please file an issue '
    'on GitHub with a reproducible sample app and the gen-l10n configuration '
    'that was used.',
  );
}
