import ee
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
        polygon (list): geometry boundary to limit the analysis
        
        polygon = [
            [[-75.081688, 6.072885],
            [-75.050185, 6.12395],
            [-75.144696, 6.121032],
            [-75.158616, 6.040785],
            [-75.081688, 6.072885]]
        ]
        
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

    
    geometry = ee.Geometry.Polygon(polygon)
    source_type = ee.data.getAsset(asset_id)["type"]
    
    if source_type == "IMAGE_COLLECTION":
        
        ee_object = ee.ImageCollection(asset_id)

        dataset = (ee_object
              .filter(ee.Filter.date(ini_date, end_date))
              .select(band)
        )

        # Calculate pixel size
        scale = dataset.first().projection().nominalScale()

        if categorical: 
            return ee.FeatureCollection(dataset.map(reduce_categorical)).toList(dataset.size()).getInfo()
        else:
            return ee.FeatureCollection(dataset.map(reduce_continuos)).toList(dataset.size()).getInfo()
    
    elif source_type == "IMAGE":
        
        dataset = ee.Image(asset_id)
        
        # Calculate pixel size
        scale = dataset.select(0).projection().nominalScale()

        if categorical: 
            return reduce_categorical(image).getInfo()
        else:
            return reduce_continuos(image).getInfo()
