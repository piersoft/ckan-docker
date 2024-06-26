/* 
 * jeoQuery v0.4
 *
 * Copyright 2012, Thomas Haukland
 * Dual licensed under the MIT or GPL Version 2 licenses.
 *
 */

var jeoquery = (function ($) {
    var my = {};

    my.defaultData = {
      userName: 'demo',
      lang: 'en'
    };
    my.defaultCountryCode = 'US';
    my.defaultLanguage = 'en';
    my.geoNamesApiServer = 'secure.geonames.org';
    my.geoNamesProtocol = 'https';

    my.featureClass = {
        AdministrativeBoundaryFeatures: 'A',
        HydrographicFeatures: 'H',
        AreaFeatures: 'L',
        PopulatedPlaceFeatures: 'P',
        RoadRailroadFeatures: 'R',
        SpotFeatures: 'S',
        HypsographicFeatures: 'T',
        UnderseaFeatures: 'U',
        VegetationFeatures: 'V'
    };

    my.getGeoNames = function(method, data, callback) {
      var deferred = $.Deferred();
      // TODO: validate method(exists), and params
        $.ajax({
            url: my.geoNamesProtocol + '://' + my.geoNamesApiServer + '/' + method + 'JSON',
            dataType: 'jsonp',
            data: $.param($.extend({}, my.defaultData, data), true),
            success: function(data) {
              deferred.resolve(data);
              if (!!callback) callback(data);
            },
            error: function (xhr, textStatus) {
              deferred.reject(xhr, textStatus);
              alert('Ooops, geonames server returned: ' + textStatus);
            }
        });
        return deferred.promise();
    }

    function formatDate(date) {
        var dateQs = '';
        if (date) {
            dateQs = date.getFullYear() + '-' + (date.getMonth() + 1) + '-' + date.getDate();
        }
        return dateQs;
    }

    var methods = {
      astergdem: {params: ['lat', 'lng'] },
      children: {params: ['geonameId', 'maxRows'] },
      cities: {params: ['north', 'south', 'east', 'west', 'lang'] },
      countryCode: {params: ['lat', 'lng', 'type', 'lang', 'radius'] },
      countryInfo: {params: ['country', 'lang'] },
      countrySubdivision: {params: ['lat', 'lng', 'level', 'lang', 'radius'] },
      earthquakes: {params: ['north', 'south', 'east', 'west', 'date', 'maxRows', 'minMagnitude'] },
      findNearby: {params: ['lat', 'lng', 'featureClass', 'featureCode', 'radius', 'style', 'maxRows'] },
      findNearbyPlacename: {params: ['lat', 'lng', 'radius', 'style'] },
      findNearbyPostalCodes: {params: ['lat', 'lng', 'radius', 'style', 'maxRows', 'country', 'localCountry', 'postalCode'] },
      findNearbyStreets: {params: ['lat', 'lng', 'radius', 'maxRows'] },
      findNearbyStreetsOSM: {params: ['lat', 'lng'] },
      findNearbyWeather: {params: ['lat', 'lng'] },
      findNearbyWikipedia: {params: ['lat', 'lng', 'radius', 'maxRows', 'country', 'postalCode'] },
      findNearestAddress: {params: ['lat', 'lng'] },
      findNearestIntersection: {params: ['lat', 'lng'] },
      findNearestIntersectionOSM: {params: ['lat', 'lng', 'radius', 'maxRows'] },
      findNearbyPOIsOSM: {params: ['lat', 'lng'] },
      get: {params: ['geonameId', 'lang', 'style'] },
      gtopo30: {params: ['lat', 'lng'] },
      hierarchy: {params: ['geonameId'] },
      neighbourhood: {params: ['lat', 'lng'] },
      neighbours: {params: ['geonameId', 'country'] },
      ocean: {params: ['lat', 'lng', 'radius'] },
      postalCodeCountryInfo: {params: [] },
      postalCodeLookup: {params: ['postalcode', 'country', 'maxRows', 'charset'] },
      postalCodeSearch: {params: ['postalcode', 'postalcode_startsWith', 'placename_startsWith', 'country', 'countryBias', 'maxRows', 'style', 'operator', 'charset', 'isReduced'] },
      search: {params: [ 'q', 'name', 'name_equals', 'name_startsWith', 'maxRows', 'startRow', 'country', 'countryBias', 'continentCode', 'adminCode1', 'adminCode2', 'adminCode3', 'featureClass', 'featureCode', 'lang', 'type', 'style', 'isNameRequired', 'tag', 'operator', 'charset', 'fuzzy'] },
      siblings: {params: ['geonameId'] },
      srtm3: {params: ['lat', 'lng'] },
      timezone: {params: ['lat', 'lng', 'radius', 'date'] },
      weather: {params: ['north', 'south', 'east', 'west', 'maxRows'] },
      weatherIcao: {params: ['ICAO'] },
      wikipediaBoundingBox: {params: ['north', 'south', 'east', 'west', 'lang', 'maxRows'] },
      wikipediaSearch: {params: ['q', 'title', 'lang', 'maxRows'] }
    };

    return my;
}(jQuery));

(function ($) {
    $.fn.jeoCountrySelect = function (options) {
        var el = this;
        $.when(jeoquery.getGeoNames('countryInfo'))
         .then(function (data) {
            var sortedNames = data.geonames;
            if (data.geonames.sort) {
                sortedNames = data.geonames.sort(function (a, b) {
                    return a.countryName.localeCompare(b.countryName);
                });
            }
            // Insert blank choice
            sortedNames.unshift({countryCode:'', countryName:''});
            var html = $.map(sortedNames, function(c) {
              return '<option value="' + c.countryCode + '">' + c.countryName + '</option>';
            });
            el.html(html);
            if (options && options.callback) options.callback(sortedNames);
        });
    };

    $.fn.jeoPostalCodeLookup = function (options) {
        this.on("change", function () {
            var code = $(this).val();
            var country = options.country || jeoquery.defaultCountryCode;
            if (options.countryInput) {
                country = options.countryInput.val() || jeoquery.defaultCountry;
            }
            if (code) {
                jeoquery.getGeoNames('postalCodeLookup', {postalcode: code, country: country}, function (data) {
                    if (data && data.postalcodes && data.postalcodes.length > 0) {
                        if (options) {
                            if (options.target) {
                                options.target.val(data.postalcodes[0].placeName);
                            }
                            if (options.callback) {
                                options.callback(data.postalcodes[0]);
                            }
                        }
                    }
                });
            }
        });
    };

    $.fn.jeoCityAutoComplete = function (options) {
        this.autocomplete({
            source: function (request, response) {
                jeoquery.getGeoNames('search', {
                    featureClass: jeoquery.featureClass.PopulatedPlaceFeatures,
                    style: "full",
                    maxRows: 12,
                    name_startsWith: request.term
                }, function (data) {
                    $(".ui-autocomplete").css("top", $("#geographical_geonames_url-view").offset().top + $("#geographical_geonames_url-view").height() + 10);
                    $(".ui-autocomplete").css("left",  $("#geographical_geonames_url-view").offset().left);
                    response(
                        $.map(data.geonames, 
                            function (item) {
                                var displayName = item.name + (item.adminName1 ? ", " + item.adminName1 : "") + ", " + item.countryName;
                                return {
                                    label: displayName,
                                    value: displayName,
                                    details: item
                                };
                            }));
                });
            },
            minLength: 2,
            select: function( event, ui ) {
              if (ui && ui.item && options && options.callback) {
                options.callback(ui.item.details);
              }
            },
            open: function () {
                $(this).removeClass("ui-corner-all").addClass("ui-corner-top");
            },
            close: function () {
                $(this).removeClass("ui-corner-top").addClass("ui-corner-all");
            }
        });
    };

})(jQuery);
