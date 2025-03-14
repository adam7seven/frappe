const WEBSITE_ROOM = "website";
const SITE_ROOM = "all";

function frappe_handlers(socket) {
	socket.join(user_room(socket.user));
	socket.join(WEBSITE_ROOM);

	if (socket.user_type == "System User") {
		socket.join(SITE_ROOM);
	}

	socket.has_permission = (doctype, id) => {
		return new Promise((resolve) => {
			socket
				.frappe_request("/api/method/frappe.realtime.has_permission", {
					doctype,
					id: id || "",
				})
				.then((res) => res.json())
				.then(({ message }) => {
					if (message) {
						resolve();
					}
				})
				.catch((err) => console.log("Can't check permissions", err));
		});
	};

	socket.on("ping", () => {
		socket.emit("pong");
	});

	socket.on("doctype_subscribe", function (doctype) {
		socket.has_permission(doctype).then(() => {
			socket.join(doctype_room(doctype));
		});
	});

	socket.on("doctype_unsubscribe", function (doctype) {
		socket.leave(doctype_room(doctype));
	});

	socket.on("task_subscribe", function (task_id) {
		const room = task_room(task_id);
		socket.join(room);
	});

	socket.on("task_unsubscribe", function (task_id) {
		const room = task_room(task_id);
		socket.leave(room);
	});

	socket.on("progress_subscribe", function (task_id) {
		const room = task_room(task_id);
		socket.join(room);
	});

	socket.on("doc_subscribe", function (doctype, docid) {
		socket.has_permission(doctype, docid).then(() => {
			socket.join(doc_room(doctype, docid));
		});
	});

	socket.on("doc_unsubscribe", function (doctype, docid) {
		let room = doc_room(doctype, docid);
		socket.leave(room);
	});

	socket.on("doc_open", function (doctype, docid) {
		socket.has_permission(doctype, docid).then(() => {
			let room = open_doc_room(doctype, docid);
			socket.join(room);
			if (!socket.subscribed_documents) socket.subscribed_documents = [];
			socket.subscribed_documents.push([doctype, docid]);

			// show who is currently viewing the form
			notify_subscribed_doc_users({
				socket: socket,
				doctype: doctype,
				docid: docid,
			});
		});
	});

	socket.on("doc_close", function (doctype, docid) {
		// remove this user from the list of 'who is currently viewing the form'
		let room = open_doc_room(doctype, docid);
		socket.leave(room);

		if (socket.subscribed_documents) {
			socket.subscribed_documents = socket.subscribed_documents.filter(([dt, dn]) => {
				!(dt == doctype && dn == docid);
			});
		}

		notify_subscribed_doc_users({
			socket: socket,
			doctype: doctype,
			docid: docid,
		});
	});

	socket.on("disconnect", () => {
		notify_disconnected_documents(socket);
	});
}

function notify_disconnected_documents(socket) {
	if (socket.subscribed_documents) {
		socket.subscribed_documents.forEach(([doctype, docid]) => {
			notify_subscribed_doc_users({ socket, doctype, docid });
		});
	}
}

function notify_subscribed_doc_users(args) {
	if (!(args && args.doctype && args.docid)) {
		return;
	}
	const socket = args.socket;
	const room = open_doc_room(args.doctype, args.docid);

	const clients = Array.from(socket.nsp.adapter.rooms.get(room) || []);

	let users = [];

	socket.nsp.sockets.forEach((sock) => {
		if (clients.includes(sock.id)) {
			users.push(sock.user);
		}
	});

	// dont send update to self. meaningless.
	if (users.length == 1 && users[0] == args.socket.user) return;

	// notify
	socket.nsp.to(room).emit("doc_viewers", {
		doctype: args.doctype,
		docid: args.docid,
		users: Array.from(new Set(users)),
	});
}

const doc_room = (doctype, docid) => "doc:" + doctype + "/" + docid;
const open_doc_room = (doctype, docid) => "open_doc:" + doctype + "/" + docid;
const user_room = (user) => "user:" + user;
const doctype_room = (doctype) => "doctype:" + doctype;
const task_room = (task_id) => "task_progress:" + task_id;

module.exports = frappe_handlers;
