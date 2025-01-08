
var initFrontend = function(serverList, currentServer) {
    window.app = new Vue({
        el: '#app',
        data: {
          serverId: currentServer,
          serverList: servers,
          loading: true,
          requesting: false,
          entries: [],
          server_status: null,
          entryRequest: null,
          entryValue: ''
        },
        created: function() {
            this.changeServer(currentServer);
        },
        methods: {
            changeServer: function() {
                console.debug("Changed server to " + this.serverId);
                this.reloadBoard();
            },

            setBoardEntries: function(entries, server_status) {
                this.loading = false;
                this.entries = entries;
                this.server_status = server_status;
            },
            reloadBoard: function() {
                if (this.entryRequest != null) {
                    this.entryRequest.abort();
                }
                console.debug("Reloading board for " + this.serverId);
                
                this.loading = true;
                var vm = this;
                
                this.entryRequest = $.getJSON( 'http://' + vm.serverList[vm.serverId] + '/entries', function( data ) {
                    vm.setBoardEntries(data.entries, data.server_status);
                }).fail(function( jqxhr, textStatus, error ) {
                    if (error !== "abort") {
                        setTimeout(function(){
                            vm.reloadBoard();
                        }, 1000)
                    }
                });
            }, 
            createEntry: function() {

                if (this.requesting) {
                    return; // wait for the previous request
                }

                console.debug("Adding entry for " + this.serverId);
                
                this.requesting = true;
                var vm = this;

                this.entryRequest = $.post( 'http://' + vm.serverList[vm.serverId] + '/entries',
                    {
                        value: vm.entryValue
                    })
                    .always(function( data ) {
                        vm.requesting = false;
                        vm.reloadBoard();
                    });
            },
            updateEntry: function(id, value) {

                if (this.requesting) {
                    return; // wait for the previous request
                }

                console.debug("Updating entry for " + this.serverId);

                this.requesting = true;
                var vm = this;

                this.entryRequest = $.post( 'http://' + vm.serverList[vm.serverId] + '/entries/' + id,
                    {
                        value: value
                    })
                    .always(function( data ) {
                        vm.requesting = false;
                        vm.reloadBoard();
                    });
            },
            deleteEntry: function(id) {

                if (this.requesting) {
                    return; // wait for the previous request
                }

                console.debug("Deleting entry for " + this.serverId);

                this.requesting = true;
                var vm = this;

                this.entryRequest = $.post( 'http://' + vm.serverList[vm.serverId] + '/entries/' + id + '/delete',
                    {
                    })
                    .always(function( data ) {
                        vm.requesting = false;
                        vm.reloadBoard();
                    });
            },
            crashServer: function() {

                if (this.requesting) {
                    return; // wait for the previous request
                }

                console.debug("Crashing server " + this.serverId);

                this.requesting = true;
                var vm = this;

                this.entryRequest = $.post( 'http://' + vm.serverList[vm.serverId] + '/crash', {})
                    .always(function( data ) {
                        vm.requesting = false;
                        vm.reloadBoard();
                    });

            },
            recoverServer: function() {

                if (this.requesting) {
                    return; // wait for the previous request
                }

                console.debug("Recovering server " + this.serverId);

                this.requesting = true;
                var vm = this;

                this.entryRequest = $.post( 'http://' + vm.serverList[vm.serverId] + '/recover', {})
                    .always(function( data ) {
                        vm.requesting = false;
                        vm.reloadBoard();
                    });
            }
        }
    });
};