'use strict';

function now() {
  return new Date().toISOString();
}

function log(tag, payload) {
  try {
    console.log(JSON.stringify({ ts: now(), tag: tag, payload: payload }));
  } catch (e) {
    console.log('[' + now() + '][' + tag + '] ' + String(payload));
  }
}

function safe(fn, fallback) {
  try {
    return fn();
  } catch (e) {
    return fallback;
  }
}

function mapToObject(map) {
  if (!map) return null;
  var out = {};
  try {
    var iterator = map.entrySet().iterator();
    while (iterator.hasNext()) {
      var entry = iterator.next();
      out[String(entry.getKey())] = String(entry.getValue());
    }
  } catch (e) {
    out._error = String(e);
  }
  return out;
}

function qvDeviceSnapshot(dev) {
  if (!dev) return null;
  return {
    umid: safe(function () { return String(dev.getUmid()); }, null),
    name: safe(function () { return String(dev.getDevName()); }, null),
    model: safe(function () { return String(dev.getModel()); }, null),
    useIp: safe(function () { return String(dev.getUseIp()); }, null),
    ip: safe(function () { return String(dev.getIp()); }, null),
    cgiPort: safe(function () { return Number(dev.getCgiPort()); }, null),
    cgiScheme: safe(function () { return Number(dev.getCgiScheme()); }, null),
    username: safe(function () { return String(dev.getUsername()); }, null),
    password: safe(function () { return String(dev.getPassword()); }, null),
    dataEncodeKey: safe(function () { return String(dev.getDataEncodeKey()); }, null),
    isHsDevice: safe(function () { return Boolean(dev.isHsDevice()); }, null),
    isVsuDevice: safe(function () { return Boolean(dev.isVsuDevice()); }, null),
    isSupportTls: safe(function () { return Boolean(dev.isSupportTls()); }, null)
  };
}

Java.perform(function () {
  log('script', 'welcomeeye_runtime_monitor loaded');

  try {
    var DownChannelManager = Java.use('com.quvii.qvweb.userauth.DownChannelManager');
    DownChannelManager.changeService.overload('java.lang.String', 'int', 'boolean').implementation = function (url, groupId, needCA) {
      log('downchannel.changeService', {
        url: String(url),
        groupId: Number(groupId),
        needCA: Boolean(needCA)
      });
      return this.changeService(url, groupId, needCA);
    };
  } catch (e) {
    log('warn', 'DownChannelManager hook unavailable: ' + e);
  }

  try {
    var QvAuthManager = Java.use('com.quvii.openapi.impl.QvAuthManager');
    QvAuthManager.handleDownChannelResponse.overload('java.lang.String').implementation = function (resp) {
      var text = String(resp);
      var lower = text.toLowerCase();
      log('downchannel.payload', {
        raw: text,
        hasBadgeKeyword: lower.indexOf('badge') >= 0 || lower.indexOf('rfid') >= 0 || lower.indexOf('card') >= 0,
        hasUnlockKeyword: lower.indexOf('unlock') >= 0 || lower.indexOf('open') >= 0 || lower.indexOf('opendoor') >= 0,
        hasCallKeyword: lower.indexOf('call') >= 0 || lower.indexOf('ring') >= 0 || lower.indexOf('visitor') >= 0
      });
      return this.handleDownChannelResponse(resp);
    };
  } catch (e) {
    log('warn', 'QvAuthManager handleDownChannelResponse hook unavailable: ' + e);
  }

  try {
    var DeviceAuthHeaderInterceptor = Java.use('com.quvii.qvweb.publico.intercept.DeviceAuthHeaderInterceptor');
    DeviceAuthHeaderInterceptor.digestAuthForUsername.overload(
      'com.quvii.publico.entity.QvDevice',
      'java.util.Map'
    ).implementation = function (dev, challengeMap) {
      var result = this.digestAuthForUsername(dev, challengeMap);
      log('device.digestAuth', {
        device: qvDeviceSnapshot(dev),
        challenge: mapToObject(challengeMap),
        authorization: String(result)
      });
      return result;
    };
  } catch (e) {
    log('warn', 'DeviceAuthHeaderInterceptor hook unavailable: ' + e);
  }

  try {
    var DeviceRequestHelp = Java.use('com.quvii.qvweb.device.DeviceRequestHelp');
    DeviceRequestHelp.openLock.overload(
      'com.quvii.publico.entity.QvDevice',
      'int',
      'java.lang.String'
    ).implementation = function (dev, door, openPassword) {
      log('device.openLock', {
        device: qvDeviceSnapshot(dev),
        door: Number(door),
        openPassword: String(openPassword)
      });
      return this.openLock(dev, door, openPassword);
    };
  } catch (e) {
    log('warn', 'DeviceRequestHelp.openLock hook unavailable: ' + e);
  }

  try {
    var RetrofitUtil = Java.use('com.quvii.qvweb.publico.utils.RetrofitUtil');
    RetrofitUtil.getDirectDeviceApi.overload('com.quvii.publico.entity.QvDevice', 'boolean').implementation = function (dev, logOpen) {
      log('device.apiTarget', {
        device: qvDeviceSnapshot(dev),
        logOpen: Boolean(logOpen)
      });
      return this.getDirectDeviceApi(dev, logOpen);
    };
  } catch (e) {
    log('warn', 'RetrofitUtil.getDirectDeviceApi hook unavailable: ' + e);
  }

  try {
    var QvDevice = Java.use('com.quvii.publico.entity.QvDevice');
    QvDevice.getDataEncodeKey.implementation = function () {
      var ret = this.getDataEncodeKey();
      log('qvdevice.getDataEncodeKey', qvDeviceSnapshot(this));
      return ret;
    };
  } catch (e) {
    log('warn', 'QvDevice.getDataEncodeKey hook unavailable: ' + e);
  }
});
