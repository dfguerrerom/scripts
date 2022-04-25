import ee
import json
ee.Initialize()

def zonal_stats(asset_id, ini_date, end_date, band, polygon, categorical=False):
    """
    Calculate zonal statistics for each of the images in input ImageCollection
    
    Args:
        asset_id (string): Image collection asset ID
        discrete (bool): Whether the input has discrete values or not (continuous, default)
        ini_date (string): Starting date to filter collection in format %YYYY-mm-dd
        end_date (string): Stop date to filter collection in format %YYYY-mm-dd
        band (string): Name of the band which cotains the target variable
        statistic (string): Reduction statistic to reduce results when using 
        polygon (geojson, str): geojson geometry
        
        {
            "type": "MultiPolygon", 
            "coordinates": [
                [[
                    [11.9948265434602, 42.6145920085208],
                    [12.1055223772636, 42.8544329817615],
                    [12.3638126561382, 42.9559041627479],
                    [11.9948265434602, 42.6145920085208]
                ]],
                [[
                    [10.7894737734482, 43.4906610302986],
                    [10.9250456000997, 43.5387118043016],
                    [11.0606174267511, 43.5867625783047],
                    [10.7894737734482, 43.4906610302986]
                ]]
            ]
        }

        
    """
    
    def reduce_categorical(image):
        """Reduce categorical type image and calculate its area"""

        # Using categorical areas
        reduced = (ee.Image.pixelArea().divide(1e4)
          .addBands(image)
          .reduceRegion(**{
            "reducer":ee.Reducer.sum().group(1), 
            "geometry":geometry,
            "scale":scale
          }
        )).get("groups")
        
        # Style output by extracting keys and values from list of dicts
        keys_values = ee.List(ee.List(reduced).map(lambda x: ee.Dictionary(x).values())).unzip()
        
        reduced = ee.Dictionary.fromLists(
            ee.List(keys_values.get(0)).map(lambda x: ee.Number(x).format()),
            keys_values.get(1), 
        )
        
        # Combine output with image info
        return ee.Feature(
            None, 
            reduced.combine(
                image.toDictionary(["system:time_start", "system:time_end", "system:id"]).rename(
                    ["system:time_start", "system:time_end", "system:id"],
                    ["system_time_start", "system_time_end", "system_id"])
            )
        )
    
    
    def reduce_continuos(image):
        """Reduce continuous type image"""

        # Using continuos
        reduced = (image
          .reduceRegion(**{
            "reducer": ee.Reducer.minMax().combine(**{
              "reducer2": ee.Reducer.mean(),
              "sharedInputs": True
            }), 
            "geometry":geometry,
            "scale": 1,
            "bestEffort": True
          }
        ))

        stats = ee.List(["min", "max", "mean"])
        append = stats.map(lambda x: ee.String("_").cat(ee.String(x)))

        from_name = append.map(lambda x: ee.String(image.bandNames().get(0)).cat(ee.String(x)))

        return ee.Feature(
            None, 
            reduced.combine(
                image.toDictionary(["system:time_start", "system:time_end", "system:id"]).rename(
                    ["system:time_start", "system:time_end", "system:id"],
                    ["system_time_start", "system_time_end", "system_id"])
            ).rename(from_name, stats)
        )
    
    # decode geojson
    decoded_polygon = json.loads(polygon)
    
    geometry = ee.Geometry.MultiPolygon(decoded_polygon["coordinates"])
    source_type = ee.data.getAsset(asset_id)["type"]
    
    if source_type == "IMAGE_COLLECTION":
        
        image_collection = (
            ee.ImageCollection(asset_id)
              .filter(ee.Filter.date(ini_date, end_date))
              .select(band)
        )

        # Get pixel size from the first image
        scale = image_collection.first().projection().nominalScale()
        
        # Use the proper reduce region function depending on the image type
        computed_object = ee.FeatureCollection(
            image_collection.map(reduce_categorical if categorical else reduce_continuos)
        ).toList(image_collection.size())
    
    elif source_type == "IMAGE":
        
        image = ee.Image(asset_id)
        
        # Get pixel size from the first image
        scale = image.select(0).projection().nominalScale()
        
        computed_object = ee.List(
            [reduce_categorical(image) if categorical else reduce_continuos(image)]
        )
        
    
    return computed_object.map(lambda x: ee.Feature(x).toDictionary()).getInfo()