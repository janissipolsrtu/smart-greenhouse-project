from smart_greenhouse.models import WateringCycle
count = WateringCycle.objects.count()
WateringCycle.objects.all().delete()
print(f'Deleted {count} watering cycles')

