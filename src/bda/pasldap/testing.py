from plone.testing import Layer
from plone.testing import Layer, zodb, zca, z2
from node.ext.ldap import testing

SITE_OWNER_NAME = SITE_OWNER_PASSWORD = 'admin'

class PASLDAPLayer(Layer):
    # big parts copied from p.a.testing!
    
    defaultBases = (testing.LDIF_groupOfNames, z2.STARTUP)

    # Products that will be installed, plus options
    products = (
            ('Products.GenericSetup'                , {'loadZCML': True}, ),
            ('Products.CMFCore'                     , {'loadZCML': True}, ),
            ('Products.PluggableAuthService'        , {'loadZCML': True}, ),
            ('Products.PluginRegistry'              , {'loadZCML': True}, ),
            ('Products.PlonePAS'                    , {'loadZCML': True}, ),
        )
    
    def setUp(self):

        # Stack a new DemoStorage on top of the one from z2.STARTUP.
        self['zodbDB'] = zodb.stackDemoStorage(self.get('zodbDB'), name='PASLDAPLayer')

        self.setUpZCML()

        # Set up products and the default content
        with z2.zopeApp() as app:
            self.setUpProducts(app)
            self.setUpDefaultContent(app)

    def tearDown(self):

        # Tear down products
        with z2.zopeApp() as app:
            # note: content tear-down happens by squashing the ZODB
            self.tearDownProducts(app)

        self.tearDownZCML()

        # Zap the stacked ZODB
        self['zodbDB'].close()
        del self['zodbDB']

    def setUpZCML(self):
        """Stack a new global registry and load ZCML configuration of Plone
        and the core set of add-on products into it. Also set the
        ``disable-autoinclude`` ZCML feature so that Plone does not attempt to
        auto-load ZCML using ``z3c.autoinclude``.
        """

        # Create a new global registry
        zca.pushGlobalRegistry()

        from zope.configuration import xmlconfig
        self['configurationContext'] = context = zca.stackConfigurationContext(self.get('configurationContext'))

        # Turn off z3c.autoinclude

        xmlconfig.string("""\
<configure xmlns="http://namespaces.zope.org/zope" xmlns:meta="http://namespaces.zope.org/meta">
    <meta:provides feature="disable-autoinclude" />
</configure>
""", context=context)

        # Load dependent products's ZCML - Plone doesn't specify dependencies
        # on Products.* packages fully

        from zope.dottedname.resolve import resolve

        def loadAll(filename):
            for p, config in self.products:
                if not config['loadZCML']:
                    continue
                try:
                    package = resolve(p)
                except ImportError:
                    continue
                try:
                    xmlconfig.file(filename, package, context=context)
                except IOError:
                    pass

        loadAll('meta.zcml')
        loadAll('configure.zcml')
        loadAll('overrides.zcml')

    def tearDownZCML(self):
        """Pop the global component registry stack, effectively unregistering
        all global components registered during layer setup.
        """
        # Pop the global registry
        zca.popGlobalRegistry()

        # Zap the stacked configuration context
        del self['configurationContext']

    def setUpProducts(self, app):
        """Install all old-style products listed in the the ``products`` tuple
        of this class.
        """

        for p, config in self.products:
            z2.installProduct(app, p)

    def tearDownProducts(self, app):
        """Uninstall all old-style products listed in the the ``products``
        tuple of this class.
        """
        for p, config in reversed(self.products):
            z2.uninstallProduct(app, p)

        # Clean up Wicked turds
        # XXX: This may tear down too much state
        try:
            from wicked.fieldevent import meta
            meta.cleanUp()
        except ImportError:
            pass

    def setUpDefaultContent(self, app):
        """Add the site owner user to the root user folder and log in as that
        user. Create the Plone site, installing the extension profiles listed
        in the ``extensionProfiles`` layer class variable. Create the test
        user inside the site, and disable the default workflow.

        Note: There is no explicit tear-down of this setup operation, because
        all persistent changes are torn down when the stacked ZODB
        ``DemoStorage`` is popped.
        """

        # Create the owner user and "log in" so that the site object gets
        # the right ownership information
        app['acl_users'].userFolderAddUser(
                SITE_OWNER_NAME,
                SITE_OWNER_PASSWORD,
                ['Manager'],
                []
            )