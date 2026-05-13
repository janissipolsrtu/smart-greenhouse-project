from .models import GreenhouseConfig


def feature_flags(request):
    """Expose active greenhouse feature flags for templates."""
    greenhouse = GreenhouseConfig.get_config()

    if not greenhouse:
        return {
            'active_greenhouse': None,
            'feature_plants_enabled': True,
            'feature_layout_enabled': True,
            'feature_meteostation_enabled': False,
            'feature_watering_liters_enabled': False,
            'feature_smart_suggestions_enabled': False,
        }

    return {
        'active_greenhouse': greenhouse,
        'feature_plants_enabled': greenhouse.feature_plants,
        'feature_layout_enabled': greenhouse.feature_layout,
        'feature_meteostation_enabled': greenhouse.feature_meteostation,
        'feature_watering_liters_enabled': greenhouse.feature_watering_liters,
        'feature_smart_suggestions_enabled': greenhouse.feature_smart_suggestions,
    }
