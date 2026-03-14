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

function qvDeviceSnapshot(dev) {
  if (!dev) return null;
  return {
    className: safe(function () { return dev.$className; }, null),
    umid: safe(function () { return String(dev.getUmid()); }, null),
    name: safe(function () { return String(dev.getDevName()); }, null),
    model: safe(function () { return String(dev.getModel()); }, null),
    host: safe(function () { return String(dev.getUseIp()); }, null),
    ip: safe(function () { return String(dev.getIp()); }, null),
    parsedIp: safe(function () { return String(dev.getParsedIp()); }, null),
    cgiPort: safe(function () { return Number(dev.getCgiPort()); }, null),
    cgiScheme: safe(function () { return Number(dev.getCgiScheme()); }, null),
    username: safe(function () { return String(dev.getUsername()); }, null),
    password: safe(function () { return String(dev.getPassword()); }, null),
    dataEncodeKey: safe(function () { return String(dev.getDataEncodeKey()); }, null),
    isHsDevice: safe(function () { return Boolean(dev.isHsDevice()); }, null),
    isVsuDevice: safe(function () { return Boolean(dev.isVsuDevice()); }, null),
    isSupportTls: safe(function () { return Boolean(dev.isSupportTls()); }, null),
    isIpDeviceSupportAuth: safe(function () { return Boolean(dev.isIpDeviceSupportAuth.value); }, null),
    authCode: safe(function () { return String(dev.getAuthCode()); }, null),
    typeOfPwdEncrypted: safe(function () { return Number(dev.getTypeOfPwdEncrypted()); }, null)
  };
}

Java.perform(function () {
  log('script', 'welcomeeye_pairing_monitor loaded');

  function qvUserSnapshot(user) {
    if (!user) return null;
    return {
      className: safe(function () { return user.$className; }, null),
      account: safe(function () { return String(user.getAccount()); }, null),
      email: safe(function () { return String(user.getEmail()); }, null),
      mobile: safe(function () { return String(user.getMobile()); }, null),
      nick: safe(function () { return String(user.getNick()); }, null),
      realName: safe(function () { return String(user.getRealName()); }, null),
      authCode: safe(function () { return String(user.getAuthCode()); }, null),
      pwd: safe(function () { return String(user.getPwd()); }, null),
      upgradeFromGuest: safe(function () { return user.getUpgradeFromGuest(); }, null)
    };
  }

  var QvDevice = null;
  try {
    QvDevice = Java.use('com.quvii.publico.entity.QvDevice');
    QvDevice.getDataEncodeKey.implementation = function () {
      var ret = this.getDataEncodeKey();
      log('qvdevice.getDataEncodeKey', qvDeviceSnapshot(this));
      return ret;
    };
  } catch (e) {
    log('warn', 'QvDevice hook unavailable: ' + e);
  }

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
    var HttpUserAuthManager = Java.use('com.quvii.qvweb.userauth.HttpUserAuthManager');

    HttpUserAuthManager.bindDevice.overload(
      'com.quvii.publico.entity.QvDevice',
      'com.quvii.qvweb.userauth.HttpUserAuthManager$OnConnectListener'
    ).implementation = function (dev, listener) {
      log('auth.bindDevice', qvDeviceSnapshot(dev));
      return this.bindDevice(dev, listener);
    };

    HttpUserAuthManager.bindHsDevice.overload(
      'com.quvii.publico.entity.QvDevice',
      'com.quvii.qvweb.userauth.HttpUserAuthManager$OnConnectListener'
    ).implementation = function (dev, listener) {
      log('auth.bindHsDevice', qvDeviceSnapshot(dev));
      return this.bindHsDevice(dev, listener);
    };

    HttpUserAuthManager.getDevDynamicPwd.overload(
      'com.quvii.publico.entity.QvDevice',
      'com.quvii.qvweb.userauth.HttpUserAuthManager$OnConnectListener'
    ).implementation = function (dev, listener) {
      log('auth.getDevDynamicPwd', qvDeviceSnapshot(dev));
      return this.getDevDynamicPwd(dev, listener);
    };
  } catch (e) {
    log('warn', 'HttpUserAuthManager hooks unavailable: ' + e);
  }

  try {
    var UserAuthRequestHelper = Java.use('com.quvii.qvweb.userauth.UserAuthRequestHelper');

    UserAuthRequestHelper.getBindDeviceReqBody.overload('com.quvii.publico.entity.QvDevice').implementation = function (dev) {
      var ret = this.getBindDeviceReqBody(dev);
      log('request.device-bind', {
        device: qvDeviceSnapshot(dev),
        requestBodyClass: safe(function () { return ret.$className; }, null)
      });
      return ret;
    };

    UserAuthRequestHelper.bindHsDevice.overload('com.quvii.publico.entity.QvDevice').implementation = function (dev) {
      var ret = this.bindHsDevice(dev);
      log('request.device-bind-hs', {
        device: qvDeviceSnapshot(dev),
        requestBodyClass: safe(function () { return ret.$className; }, null)
      });
      return ret;
    };

    UserAuthRequestHelper.getDevDynamicPwd.overload('com.quvii.publico.entity.QvDevice').implementation = function (dev) {
      var ret = this.getDevDynamicPwd(dev);
      log('request.get-device-token', {
        device: qvDeviceSnapshot(dev),
        requestBodyClass: safe(function () { return ret.$className; }, null)
      });
      return ret;
    };
  } catch (e) {
    log('warn', 'UserAuthRequestHelper hooks unavailable: ' + e);
  }

  try {
    var QvAuthManager = Java.use('com.quvii.openapi.impl.QvAuthManager');
    QvAuthManager.dealWithLoginResp.overload(
      'com.quvii.qvweb.publico.entity.QvUser',
      'com.quvii.qvweb.userauth.bean.response.UserLoginResp',
      'com.quvii.publico.common.LoadListener'
    ).implementation = function (user, resp, listener) {
      log('auth.login.response', {
        sessionId: safe(function () { return String(resp.getHeader().getSession().getId()); }, null),
        result: safe(function () { return Number(resp.getHeader().getResult()); }, null),
        accountId: safe(function () { return String(resp.getContent().getAccountId()); }, null),
        token: safe(function () { return String(resp.getContent().getToken()); }, null),
        ipRegionId: safe(function () { return Number(resp.getContent().getIpRegionId()); }, null)
      });
      return this.dealWithLoginResp(user, resp, listener);
    };
  } catch (e) {
    log('warn', 'QvAuthManager login hook unavailable: ' + e);
  }

  try {
    var QvOpenSDK = Java.use('com.quvii.openapi.QvOpenSDK');

    QvOpenSDK.accountRegisterSendVerifyCode.overload(
      'java.lang.String',
      'com.quvii.publico.common.SimpleLoadListener'
    ).implementation = function (account, listener) {
      log('signup.send_register_code.phone', {
        account: String(account)
      });
      return this.accountRegisterSendVerifyCode(account, listener);
    };

    QvOpenSDK.accountRegisterSendEmailVerifyCode.overload(
      'java.lang.String',
      'com.quvii.publico.common.SimpleLoadListener'
    ).implementation = function (account, listener) {
      log('signup.send_register_code.email', {
        account: String(account)
      });
      return this.accountRegisterSendEmailVerifyCode(account, listener);
    };

    QvOpenSDK.accountRegisterByPhoneNum.overload(
      'java.lang.String',
      'java.lang.String',
      'java.lang.String',
      'java.lang.Integer',
      'com.quvii.publico.common.SimpleLoadListener'
    ).implementation = function (account, password, code, upgradeFromGuest, listener) {
      log('signup.register.phone', {
        account: String(account),
        password: String(password),
        authCode: String(code),
        upgradeFromGuest: upgradeFromGuest ? Number(upgradeFromGuest) : null
      });
      return this.accountRegisterByPhoneNum(account, password, code, upgradeFromGuest, listener);
    };

    QvOpenSDK.accountRegisterByEmail.overload(
      'java.lang.String',
      'java.lang.String',
      'java.lang.String',
      'java.lang.String',
      'java.lang.Integer',
      'com.quvii.publico.common.SimpleLoadListener'
    ).implementation = function (account, password, nick, code, upgradeFromGuest, listener) {
      log('signup.register.email', {
        account: String(account),
        password: String(password),
        nick: String(nick),
        authCode: String(code),
        upgradeFromGuest: upgradeFromGuest ? Number(upgradeFromGuest) : null
      });
      return this.accountRegisterByEmail(account, password, nick, code, upgradeFromGuest, listener);
    };
  } catch (e) {
    log('warn', 'QvOpenSDK signup hooks unavailable: ' + e);
  }

  try {
    var HttpUserAuthManager = Java.use('com.quvii.qvweb.userauth.HttpUserAuthManager');
    HttpUserAuthManager.accountRegister.overload(
      'com.quvii.qvweb.publico.entity.QvUser',
      'int',
      'com.quvii.qvweb.userauth.HttpUserAuthManager$OnConnectListener'
    ).implementation = function (user, activeWay, listener) {
      log('auth.accountRegister', {
        activeWay: Number(activeWay),
        user: qvUserSnapshot(user)
      });
      return this.accountRegister(user, activeWay, listener);
    };
  } catch (e) {
    log('warn', 'HttpUserAuthManager accountRegister hook unavailable: ' + e);
  }

  try {
    var QvLocationManager = Java.use('com.quvii.qvweb.userauth.QvLocationManager');
    QvLocationManager.switchToTargetGroup.overload('int').implementation = function (groupId) {
      log('location.switchToTargetGroup', { groupId: Number(groupId) });
      return this.switchToTargetGroup(groupId);
    };
  } catch (e) {
    log('warn', 'QvLocationManager hook unavailable: ' + e);
  }

  try {
    var UserAuthRequestHelper = Java.use('com.quvii.qvweb.userauth.UserAuthRequestHelper');
    UserAuthRequestHelper.getAccountRegisterReqBody.overload(
      'com.quvii.qvweb.publico.entity.QvUser',
      'java.lang.String'
    ).implementation = function (user, activeWay) {
      var ret = this.getAccountRegisterReqBody(user, activeWay);
      log('request.account-register', {
        activeWay: String(activeWay),
        user: qvUserSnapshot(user),
        requestBodyClass: safe(function () { return ret.$className; }, null)
      });
      return ret;
    };

    UserAuthRequestHelper.userAuthByPhone.overload(
      'java.lang.String',
      'java.lang.String'
    ).implementation = function (phone, authType) {
      var ret = this.userAuthByPhone(phone, authType);
      log('request.send-register-code.phone', {
        phone: String(phone),
        authType: String(authType),
        requestBodyClass: safe(function () { return ret.$className; }, null)
      });
      return ret;
    };
  } catch (e) {
    log('warn', 'UserAuthRequestHelper signup request hooks unavailable: ' + e);
  }

  try {
    var QvUserAuthCore = Java.use('com.quvii.core.QvUserAuthCore');
    QvUserAuthCore.handleDownChannelResponse.overload('java.lang.String').implementation = function (payload) {
      var text = String(payload);
      if (
        text.indexOf('account-register') >= 0 ||
        text.indexOf('send-register-code') >= 0 ||
        text.indexOf('register') >= 0 ||
        text.indexOf('verify') >= 0
      ) {
        log('downchannel.signup.payload', text);
      }
      return this.handleDownChannelResponse(payload);
    };
  } catch (e) {
    log('warn', 'QvUserAuthCore signup response hook unavailable: ' + e);
  }
});
