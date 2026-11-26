'use strict';
'require view';
'require form';
'require uci';
'require fs';
'require ui';

return view.extend({
	load: function() {
		return uci.load('nfc_wifi');
	},

	render: function() {
		var m, s, o;

		m = new form.Map('nfc_wifi', _('NFC 标签同步'),
			_('把当前 WiFi 名称和密码写入路由器的 NFC 标签，手机碰一下即可自动连接。') +
			'<br /><br />' +
			_('支持硬件：小米 AX3000T（FM11NT082C，I2C 总线 0、地址 0x57）。') +
			_('其他机型可在 <code>/etc/config/nfc_wifi</code> 中修改 <code>bus</code> 与 <code>address</code>。'));

		s = m.section(form.NamedSection, 'main', 'nfc_wifi', _('设置'));
		s.anonymous = true;
		s.addremove = false;

		o = s.option(form.Flag, 'enabled', _('启用自动同步'));
		o.default = '1';
		o.rmempty = false;
		o.description = _('开启后：开机时、以及修改 WiFi 名称或密码后，自动更新 NFC 标签。');

		o = s.option(form.Value, 'bus', _('I2C 总线'), _('留空使用默认值 0'));
		o.placeholder = '0';
		o.datatype = 'uinteger';
		o.rmempty = true;

		o = s.option(form.Value, 'address', _('标签地址'),
			_('十六进制，需带 0x 前缀。留空使用默认值 0x57'));
		o.placeholder = '0x57';
		o.rmempty = true;
		o.validate = function(section_id, value) {
			if (value == null || value === '')
				return true;
			if (!/^0x[0-9a-fA-F]{1,2}$/.test(value))
				return _('请填写 0x 开头的十六进制地址，例如 0x57');
			return true;
		};

		o = s.option(form.Button, '_syncnow', _('手动同步'));
		o.inputtitle = _('立即同步');
		o.inputstyle = 'apply';
		o.onclick = function() {
			return fs.exec('/usr/sbin/nfc-wifi-sync', [ '--force' ]).then(function(res) {
				if (res.code === 0)
					ui.addNotification(null, E('p', _('同步完成')), 'info');
				else
					ui.addNotification(null, E('p', _('同步失败 (exit %d)，详情见系统日志：logread | grep nfc-wifi').format(res.code)), 'danger');
			}).catch(function(e) {
				ui.addNotification(null, E('p', _('同步失败：%s').format(e.message)), 'danger');
			});
		};

		return m.render();
	}
});
